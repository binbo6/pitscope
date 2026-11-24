from __future__ import annotations

import json
import logging
import mimetypes
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analysis import analyze_case, read_points
from .assistant import answer, get_case, session_history, now
from .bootstrap import seed, portable_path
from .knowledge import connect, documents, ingest, index
from .reporting import safe_html, docx_bytes, pdf_bytes, html_document
from .settings import DATA, ROOT, model_settings

# Windows registry may register .js as text/plain, blocked by nosniff.
mimetypes.add_type('application/javascript','.js')
mimetypes.add_type('text/css','.css')
mimetypes.add_type('image/svg+xml','.svg')


@asynccontextmanager
async def lifespan(app):
    seed()
    yield


app=FastAPI(title='PitScope · 基坑工程知识助手',version='0.1.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','testserver'])


@app.middleware('http')
async def local_origin(request: Request,call_next):
    # No public CORS. Reject browser requests from other origins to the local service.
    origin=request.headers.get('origin')
    if origin and origin not in (f'http://{request.headers.get("host")}',f'https://{request.headers.get("host")}'):
        return Response('Cross-origin requests disabled',status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@app.get('/',response_class=HTMLResponse)
def home():return (ROOT/'web/index.html').read_text(encoding='utf-8')


@app.get('/api/status')
def status():
    cfg=model_settings();docs=documents()
    return {'app':'PitScope','version':'0.1.0','model_configured':bool(cfg['key']) or 'localhost' in cfg['base_url'] or '127.0.0.1' in cfg['base_url'],
            'model':cfg['model'],'documents':len(docs),'chunks':sum(d['chunks'] for d in docs),
            'retrieval':'本地 TF-IDF 向量 + BM25 + RRF','default_case':'DEMO-PIT-001'}


@app.get('/api/documents')
def list_docs():return documents()


@app.post('/api/documents')
async def upload_document(file:UploadFile=File(...),kind:Literal['geotech','standard','project','reference']=Form('reference'),
                          scope:str=Form('reference')):
    if scope not in ('demo','reference'):
        try:get_case(scope)
        except ValueError as exc:raise HTTPException(400,'请选择有效的资料关联案例') from exc
    filename=Path((file.filename or '').replace('\\','/')).name
    if Path(filename).suffix.lower() not in {'.pdf','.docx','.txt','.md'}:
        raise HTTPException(400,'支持 PDF / DOCX / TXT / MD')
    payload=await file.read(20*1024*1024+1)
    if len(payload)>20*1024*1024:raise HTTPException(413,'单个文档上限 20 MB')
    folder=DATA/'uploads'/uuid.uuid4().hex[:12];folder.mkdir(parents=True)
    path=folder/filename;path.write_bytes(payload)
    try:return ingest(path,name=filename,kind=kind,scope=scope,note='用户上传；版本与工程适用性待核实。')
    except Exception as exc:
        raise HTTPException(400,'无法提取有效文本，请检查文件格式；扫描件需先做 OCR。') from exc


@app.get('/api/search')
def search(q:str,reference:bool=False):
    if len(q)>3000:raise HTTPException(400,'检索问题过长')
    return index.search(q,limit=8,include_reference=reference)


@app.get('/api/sources/{document_id}')
def source_file(document_id:str):
    with connect() as db:row=db.execute('SELECT path,name FROM documents WHERE id=?',(document_id,)).fetchone()
    if not row:raise HTTPException(404,'资料不存在')
    return FileResponse(row['path'],filename=row['name'],content_disposition_type='inline')


@app.get('/api/cases')
def cases():
    result=[]
    for path in (DATA/'cases').glob('*/case.json'):
        c=json.loads(path.read_text(encoding='utf-8'))
        result.append({k:c[k] for k in ('id','name','is_demo')})
    return sorted(result,key=lambda x:not x['is_demo'])


@app.get('/api/case')
def case(case_id:str='DEMO-PIT-001'):
    try:
        c=get_case(case_id);return {'case':c,'analysis':analyze_case(c)}
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@app.post('/api/cases/import')
async def import_case(ground:UploadFile=File(...),bottom:UploadFile|None=File(None),project_name:str=Form('用户导入位移案例')):
    ident='USER-'+uuid.uuid4().hex[:12];folder=DATA/'cases'/ident;folder.mkdir(parents=True)
    stage={'id':'S1','name':'导入工况（施工阶段未核实）','date':'未提供','depth_m':'未提供'}
    for region,file in [('ground',ground),('bottom',bottom)]:
        if not file:continue
        data=await file.read(20*1024*1024+1)
        if len(data)>20*1024*1024:raise HTTPException(413,'CSV 上限 20 MB')
        path=folder/f'{region}.csv';path.write_bytes(data)
        try:read_points(path)
        except (ValueError,UnicodeError) as exc:raise HTTPException(400,str(exc)) from exc
        stage[region]=portable_path(path)
    c={'id':ident,'name':project_name[:100],'is_demo':False,'location':'未核实','depth_m':'未提供',
       'support':'未提供','baseline':'未提供，待核实','description':'用户 CSV，真实性及工况待核实',
       'quality':{'data_type':'user_unverified','solver_run':False,'project_linkage_verified':False,
                  'note':'用户导入；坐标约定按 +Y 向下解析，未核实工程同一性、基准及求解质量。'},
       'stages':[stage],'controls':{}}
    (folder/'case.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'id':ident,'name':c['name']}


class ChatRequest(BaseModel):
    question:str=Field(min_length=1,max_length=6000)
    session_id:str|None=Field(default=None,max_length=80)
    mode:Literal['qa','analysis','report']='qa'
    engine:Literal['auto','offline']='auto'
    case_id:str='DEMO-PIT-001'
    reference:bool=False


@app.post('/api/chat')
def chat(body:ChatRequest):
    try:
        response=answer(**body.model_dump())
        response['html']=safe_html(response['content'])
        return response
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@app.get('/api/sessions')
def sessions():
    with connect() as db:return [dict(r) for r in db.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT 30')]


@app.get('/api/sessions/{session_id}')
def messages(session_id:str):
    result=session_history(session_id)
    for r in result:
        r['meta']=json.loads(r['meta']);r['html']=safe_html(r['content'])
    return result


@app.get('/api/reports')
def reports():
    with connect() as db:return [dict(r) for r in db.execute('SELECT id,title,created_at FROM reports ORDER BY created_at DESC')]


@app.get('/api/reports/{report_id}/{fmt}')
def download_report(report_id:str,fmt:Literal['md','html','docx','pdf','json']):
    with connect() as db:row=db.execute('SELECT * FROM reports WHERE id=?',(report_id,)).fetchone()
    if not row:raise HTTPException(404,'报告不存在')
    text=row['markdown']
    if fmt=='md':data,mime=text.encode('utf-8'),'text/markdown; charset=utf-8'
    elif fmt=='html':data,mime=html_document(text).encode('utf-8'),'text/html; charset=utf-8'
    elif fmt=='docx':data,mime=docx_bytes(text),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif fmt=='pdf':data,mime=pdf_bytes(text),'application/pdf'
    else:data,mime=row['meta'].encode('utf-8'),'application/json; charset=utf-8'
    return Response(data,media_type=mime,headers={'Content-Disposition':f'attachment; filename="PitScope-{report_id}.{fmt}"'})


app.mount('/assets',StaticFiles(directory=str(ROOT/'web')),name='assets')
