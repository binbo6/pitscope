from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta

from . import llm
from .analysis import analyze_case
from .bootstrap import load_case
from .knowledge import connect, index
from .reporting import report_text, evidence_list, result_table
from .settings import DATA


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def get_case(case_id='DEMO-PIT-001'):
    if case_id == 'DEMO-PIT-001':return load_case()
    if not re.fullmatch(r'USER-[a-f0-9]{12}',case_id):raise ValueError('案例编号无效')
    path=DATA/'cases'/case_id/'case.json'
    if not path.exists():raise ValueError('案例不存在')
    return json.loads(path.read_text(encoding='utf-8'))


def session_history(session_id):
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT role,content,meta FROM messages WHERE session_id=? ORDER BY id',(session_id,))]


def evidence_for(query,report=False,reference=False,case_id='DEMO-PIT-001'):
    scopes=['hubei','wuhan','general', 'demo' if case_id=='DEMO-PIT-001' else case_id]
    first=index.search(query,limit=6,include_reference=reference,scopes=scopes)
    if report:
        extras=[]
        for topic,kind in [('基坑地质结构 淤泥质土 地下水','geotech'),('竖向位移 监测 数据处理 成果 报告','standard')]:
            extras += index.search(topic,limit=2,include_reference=False,kind=kind,scopes=scopes)
        seen={x['id'] for x in first}
        first.extend(x for x in extras if x['id'] not in seen)
    for i,x in enumerate(first,1):x['citation']=f'E{i}'
    return first


def extractive_answer(query,evidence,analysis,mode='qa'):
    """Honest fallback: deterministic analysis plus quoted retrieval, not simulated LLM."""
    lines=['**证据摘录模式**：本次未使用大模型，以下由程序计算与本地检索生成。','']
    if mode=='analysis' or any(x in query for x in ('沉降','隆起','数值','结果','阶段','超限','报告')):
        lines += [result_table(analysis),'','以上为当前案例 CSV 统计。[D1]']
        for c in analysis['checks']:
            lines.append(f"{c['label']}为 {c['actual_mm']:.3f} mm，比较阈值 {c['limit_mm']:.3f} mm，{'超过' if c['exceeded'] else '未超过'}所设阈值。来源：{c['source']}。")
    if evidence:
        lines += ['','可核查的相关资料：','']
        for e in evidence[:4]:
            text=e['text'][:650].replace('\n',' ')
            lines += [f"**[{e['citation']}] {e['name']}**",f'> {text}','']
        lines.append('以上为相关原文摘录，具体适用性应结合资料范围核对。')
    else:
        lines.append('当前知识库未检索到直接依据，请导入相关规范或项目资料。')
    if analysis['is_demo']:
        lines.append('本案例使用合成位移与人为设定阈值，仅用于流程演示。')
    return '\n'.join(lines)


def validate_citations(text,evidence):
    allowed={x['citation'] for x in evidence} | {'D1'}
    unknown=set(re.findall(r'\[(E\d+|D\d+)\]',text))-allowed
    if unknown:raise ValueError('模型生成了不存在的证据编号')


def clean_model_text(text):
    # Citation metadata comes from the retriever; discard a model-written duplicate bibliography.
    heading=r'(?m)^\s*(?:#{1,6}\s*|\*\*)(?:引用来源|参考来源|参考文献|参考资料|证据来源|资料来源)[^\n]*\n'
    return re.split(heading,text,maxsplit=1)[0].rstrip()


def answer(question,session_id=None,mode='qa',engine='auto',case_id='DEMO-PIT-001',reference=False):
    session_id=session_id or uuid.uuid4().hex
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?,?)',(session_id,question[:40],now()))
    history=session_history(session_id)
    if any(json.loads(x['meta']).get('case_id',case_id)!=case_id for x in history if x['role']=='assistant'):
        raise ValueError('切换案例后请开始新的对话，避免混用工程上下文。')
    case=get_case(case_id);analysis=analyze_case(case)
    report=mode=='report'
    # Resolve short follow-ups using earlier USER questions, not generated statements.
    followup=any(term in question for term in ('这些','上述','继续','刚才','这个','进一步','这一'))
    previous=next((x['content'] for x in reversed(history) if x['role']=='user'),'')[-500:] if followup else ''
    query=question+' '+previous
    evidence=evidence_for(query,report,reference,case_id)
    if followup:
        prior=next((json.loads(x['meta']).get('evidence',[]) for x in reversed(history) if x['role']=='assistant'),[])
        seen={x['id'] for x in evidence}
        evidence.extend(x for x in prior if x['kind']=='standard' and x['id'] not in seen)
        for i,e in enumerate(evidence,1):e['citation']=f'E{i}'
    if report:
        directive=('请为基坑工程报告撰写“变形特征、工程解释与监测建议”一节，约 600～900 字。'
                   '用四个连贯正文段落，不加本节标题、不单设结论和来源清单。数据性质、方法与限制已在报告固定章节说明，避免逐段重复。'
                   '结合阶段数据、极值位置、勘察地层与环境、地下水、可验证规范条文。'
                   '给出可实施的复核方向，但不要虚构已实施的监测。无需重复整份报告。用户要求：'+question)
    elif mode=='analysis':
        directive='按“数值结果—阶段特征—资料解释—复核建议”组织可放入报告的分析段落。'+question
    else:directive=question
    warning=None
    try:
        if engine=='offline':raise RuntimeError('用户选择证据摘录模式')
        content,used=llm.generate(directive,evidence,analysis,history)
        content=clean_model_text(content)
        validate_citations(content,evidence)
    except Exception as exc:
        if engine!='offline':
            warning='模型暂时不可用，已使用可离线复算的证据摘录模式。'
            logging.warning('LLM fallback: %s',type(exc).__name__)
        content=extractive_answer(question,evidence,analysis,'analysis' if report else mode)
        used='offline-extractive'
    if case['is_demo'] and '演示' not in content:
        content='本案例为合成数据流程演示。\n\n'+content
    report_id=None
    if report:
        report_id=uuid.uuid4().hex[:16]
        content=report_text(case,analysis,evidence,content,used)
        folder=DATA/'reports'/report_id;folder.mkdir(parents=True,exist_ok=True)
        meta={'engine':used,'case_id':case_id,'is_demo':case['is_demo'],'evidence':evidence,
              'analysis':analysis,'question':question,'created_at':now()}
        (folder/'report.md').write_text(content,encoding='utf-8')
        (folder/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        with connect() as db:
            db.execute('INSERT INTO reports VALUES (?,?,?,?,?)',
                       (report_id,case['name']+' · 分析报告',content,json.dumps(meta,ensure_ascii=False),now()))
    else:
        content += '\n\n<REFERENCES_PLACEHOLDER>'
        content=content.replace('<REFERENCES_PLACEHOLDER>', '**引用来源**\n\n'+evidence_list(evidence))
    meta={'evidence':evidence,'engine':used,'warning':warning,'report_id':report_id,'case_id':case_id}
    with connect() as db:
        db.execute('INSERT INTO messages(session_id,role,content) VALUES (?,?,?)',(session_id,'user',question))
        db.execute('INSERT INTO messages(session_id,role,content,meta) VALUES (?,?,?,?)',
                   (session_id,'assistant',content,json.dumps(meta,ensure_ascii=False)))
    return {'session_id':session_id,'content':content,**meta}
