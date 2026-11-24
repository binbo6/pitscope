'use strict';
const $ = s => document.querySelector(s);
const state = { session:null, caseId:'DEMO-PIT-001', busy:false, evidence:[], reports:[], case:null };
const escapeText = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url, options={}) {
  const response = await fetch(url, options);
  if (!response.ok) { let msg; try {msg=(await response.json()).detail;} catch {msg='请求失败，请检查本地服务。';} throw Error(typeof msg==='string'?msg:JSON.stringify(msg)); }
  return response.json();
}
let toastTimer;
function toast(msg) {$('#toast').textContent=msg;$('#toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').style.display='none',6000);}
function view(name) {document.querySelectorAll('.view').forEach(e=>e.classList.toggle('active',e.id==='view-'+name));document.querySelectorAll('.nav-item').forEach(e=>e.classList.toggle('active',e.dataset.view===name));$('#page-title').textContent={chat:'专业对话',knowledge:'工程知识库',reports:'成果报告'}[name];if(name==='knowledge')loadDocuments();if(name==='reports')loadReports();}
document.querySelectorAll('[data-view]').forEach(e=>e.addEventListener('click',()=>view(e.dataset.view)));
function newChat() {if(state.busy)return toast('当前回答完成后即可开始新的分析。');state.session=null;state.evidence=[];$('#messages').replaceChildren();$('#welcome').hidden=false;$('#question').value='';view('chat');window.scrollTo({top:0});}
$('#new-chat').addEventListener('click',newChat);
$('#mobile-new').addEventListener('click',newChat);
function message(role,content,meta={}) {
  $('#welcome').hidden=true;
  const item=document.createElement('article');item.className='message '+role;
  if(role==='user') {const t=document.createElement('div');t.className='message-text';t.textContent=content;item.append(t);} else {
    const label=document.createElement('div');label.className='assistant-label';label.innerHTML='◈ &nbsp; PitScope <span>'+escapeText(meta.engine==='offline-extractive'?'证据摘录':'工程分析')+'</span>';
    const text=document.createElement('div');text.className='message-text';text.innerHTML=meta.html||'';
    const actions=document.createElement('div');actions.className='message-actions';
    const copy=document.createElement('button');copy.textContent='复制正文';copy.onclick=()=>navigator.clipboard.writeText(content).then(()=>toast('已复制报告正文。')).catch(()=>toast('复制失败，请手动选择正文。'));
    const evidence=document.createElement('button');evidence.textContent='查看依据 · '+(meta.evidence?.length||0);evidence.onclick=()=>showEvidence(meta.evidence||[]);
    actions.append(copy,evidence);
    if(meta.report_id) for(const fmt of ['docx','pdf','md']) {const a=document.createElement('a');a.href=`/api/reports/${meta.report_id}/${fmt}`;a.textContent='下载 '+fmt.toUpperCase();actions.append(a);}
    item.append(label,text,actions);
  }
  $('#messages').append(item);return item;
}
async function send(question,mode) {
  if(state.busy || !question.trim())return;
  state.busy=true;view('chat');$('#send').disabled=true;$('#case-select').disabled=true;$('#question').value='';
  message('user',question);
  const loading=document.createElement('div');loading.className='loading';loading.innerHTML='<span class="spinner"></span><span>检索资料、计算位移并生成分析…</span>';$('#messages').append(loading);loading.scrollIntoView({behavior:'smooth',block:'center'});
  try {
    const r=await api('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,session_id:state.session,mode:mode||$('#mode').value,engine:$('#engine').value,case_id:state.caseId})});
    state.session=r.session_id;state.evidence=r.evidence;loading.remove();const item=message('assistant',r.content,r);item.scrollIntoView({behavior:'smooth',block:'start'});if(r.warning)toast(r.warning);await Promise.all([loadHistory(),loadReports()]);
  } catch(e) {loading.remove();toast(e.message);$('#question').value=question;}
  finally {state.busy=false;$('#send').disabled=false;$('#case-select').disabled=false;}
}
$('#chat-form').addEventListener('submit',e=>{e.preventDefault();send($('#question').value);});
$('#question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send($('#question').value);}});
document.querySelectorAll('[data-question]').forEach(e=>e.addEventListener('click',()=>{$('#mode').value=e.dataset.mode;send(e.dataset.question,e.dataset.mode);}));
$('#create-report').onclick=()=>send('请结合当前案例的勘察、规范与 CSV 数据，生成完整的基坑沉降与坑底隆起监测分析报告。','report');
function showEvidence(evidence) {
  const target=$('#evidence-list');target.replaceChildren();
  if(!evidence.length)target.innerHTML='<p class="empty-state">尚无本次回答证据。可先开始专业问答，或在知识库检索资料。</p>';
  for(const e of evidence)target.append(evidenceCard(e));
  $('#evidence-dialog').showModal();
}
function evidenceCard(e) {
  const card=document.createElement('div');card.className='evidence-card';
  const where=e.page?'PDF 第 '+e.page+' 页':e.section;
  card.innerHTML=`<strong>[${escapeText(e.citation)}] ${escapeText(e.name)}</strong><small>${escapeText(where)} · ${escapeText(e.scope)}</small><p>${escapeText(e.text)}</p><small>${escapeText(e.note)}</small><p><a href="/api/sources/${encodeURIComponent(e.document_id)}${e.page?'#page='+e.page:''}" target="_blank" rel="noopener">打开原始资料 ↗</a></p>`;
  return card;
}
$('#sources-toggle').onclick=()=>showEvidence(state.evidence);
async function loadHistory() {
  const rows=await api('/api/sessions');$('#history').replaceChildren();
  for(const r of rows.slice(0,10)){const b=document.createElement('button');b.textContent='◌  '+r.title;b.title=r.title;b.onclick=async()=>{
    if(state.busy)return;try {const rows=await api('/api/sessions/'+r.id);state.session=r.id;$('#messages').replaceChildren();view('chat');
      const last=rows.filter(x=>x.role==='assistant').at(-1);if(last?.meta?.case_id){state.caseId=last.meta.case_id;$('#case-select').value=state.caseId;await loadCase();}
      for(const m of rows)message(m.role,m.content,{...m.meta,html:m.html});state.evidence=last?.meta?.evidence||[];
    } catch(e){toast(e.message);}
  };$('#history').append(b);}
}
async function loadCases(selected) {
  const rows=await api('/api/cases');$('#case-select').replaceChildren();for(const c of rows){const o=document.createElement('option');o.value=c.id;o.textContent=c.name;$('#case-select').append(o);}if(selected)state.caseId=selected;$('#case-select').value=state.caseId;await loadCase();
}
async function loadCase() {
  const {case:c,analysis:a}=await api('/api/case?case_id='+encodeURIComponent(state.caseId));state.case=c;
  const g=a.latest.regions.ground,b=a.latest.regions.bottom;
  $('#ground-metric').innerHTML=g.max_downward_mm.toFixed(1)+'<em>mm</em>';$('#bottom-metric').innerHTML=(b?b.max_upward_mm.toFixed(1):'—')+'<em>mm</em>';
  $('#ground-status').textContent=c.is_demo?'演示阈值 '+c.controls.ground.limit_mm+' mm':'无已核实控制值';$('#bottom-status').textContent=c.is_demo?'演示阈值 '+c.controls.bottom.limit_mm+' mm':(b?'无已核实控制值':'未提供坑底 CSV');
  $('#case-banner').innerHTML=c.is_demo?'<span>◉</span><div><strong>流程演示 · 合成数据</strong><small>背景与位移均为公开合成示例</small></div>':'<span>◉</span><div><strong>用户导入 · 工程条件待核实</strong><small>真实性、位移基准与求解质量待核实</small></div>';
  $('#case-description').textContent=c.description;$('#latest-stage').textContent=a.latest.id;$('#context-chip').textContent=c.is_demo?'已关联演示案例':'已关联导入案例';$('#csv-description').textContent=`地表 ${g.count} 节点 · ${a.stages.length} 阶段`;
  renderChart(a);
}
$('#case-select').onchange=async()=>{if(state.busy)return;state.caseId=$('#case-select').value;newChat();try{await loadCase();}catch(e){toast(e.message);}};
function renderChart(a) {
  const w=230,h=120,p=22,values=a.stages.map(s=>[s.regions.ground?.max_downward_mm||0,s.regions.bottom?.max_upward_mm||0]);
  const max=Math.max(5,...values.flat())*1.18;const x=i=>p+(w-2*p)*(values.length===1?.5:i/(values.length-1));const y=v=>h-22-(h-36)*v/max;
  let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="各阶段地表最大沉降和坑底最大隆起，单位毫米">`;
  for(let i=0;i<4;i++){const val=max*i/3;svg+=`<line x1="${p}" x2="${w-p}" y1="${y(val)}" y2="${y(val)}" stroke="#dbe2d3" stroke-dasharray="2 3"/><text x="1" y="${y(val)+3}" font-size="7" fill="#9ba88f">${val.toFixed(0)}</text>`;}
  for(let j=0;j<2;j++){const color=j?'#66836b':'#b18a4a';svg+=`<polyline points="${values.map((v,i)=>x(i)+','+y(v[j])).join(' ')}" fill="none" stroke="${color}" stroke-width="1.6"/>`;values.forEach((v,i)=>{svg+=`<circle cx="${x(i)}" cy="${y(v[j])}" r="2.3" fill="${color}"><title>${escapeText(a.stages[i].id)}: ${v[j].toFixed(3)} mm</title></circle>`;});}
  a.stages.forEach((s,i)=>svg+=`<text x="${x(i)}" y="115" text-anchor="middle" font-size="8" fill="#91a080">${escapeText(s.id)}</text>`);$('#stage-chart').innerHTML=svg+'</svg>';
}
const kinds={geotech:'勘察报告',standard:'工程规范',method:'分析方法',project:'项目资料',reference:'参考资料'};
async function loadDocuments(){const docs=await api('/api/documents');$('#doc-count').textContent=String(docs.length).padStart(2,'0');$('#coverage-count').textContent=docs.length+' 份资料';$('#document-list').replaceChildren();for(const d of docs){const card=document.createElement('article');card.className='document-card';card.innerHTML=`<div class="card-top"><h3>${escapeText(d.name)}</h3><a class="card-link" href="/api/sources/${encodeURIComponent(d.id)}" target="_blank" rel="noopener">查看原文 ↗</a></div><p>${escapeText(d.note)}</p><div class="card-tags"><span>${escapeText(kinds[d.kind]||d.kind)}</span><span>${d.chunks} 个片段</span><span>${d.pages?d.pages+' 页':'文本资料'}</span><span>${d.scope==='reference'?'异项目参考 · 默认排除':escapeText(d.scope)}</span></div>`;$('#document-list').append(card);}}
$('#search-button').onclick=async()=>{const q=$('#search-query').value.trim();if(!q)return;try{const results=await api('/api/search?q='+encodeURIComponent(q));$('#search-results').replaceChildren();if(!results.length)$('#search-results').innerHTML='<p class="empty-state">没有找到直接相关的资料。</p>';for(const e of results)$('#search-results').append(evidenceCard(e));}catch(e){toast(e.message);}};
$('#search-query').onkeydown=e=>{if(e.key==='Enter')$('#search-button').click();};
async function loadReports(){const reports=await api('/api/reports');state.reports=reports;$('#report-count').textContent=String(reports.length).padStart(2,'0');$('#report-list').replaceChildren();if(!reports.length)$('#report-list').innerHTML='<p class="empty-state">点击上方按钮，生成第一份带数据与证据的工程报告。</p>';for(const r of reports){const card=document.createElement('article');card.className='report-card';card.innerHTML=`<div class="card-top"><h3>▧ &nbsp; ${escapeText(r.title)}</h3></div><p>${escapeText(r.created_at.replace('T',' '))} · 报告初稿 · 含证据归档</p><div class="message-actions">${['docx','pdf','md','html','json'].map(f=>`<a href="/api/reports/${encodeURIComponent(r.id)}/${f}">${f==='json'?'证据 JSON':f.toUpperCase()}</a>`).join('')}</div>`;$('#report-list').append(card);}}
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
$('#upload-doc-open').onclick=()=>$('#upload-dialog').showModal();$('#import-csv-open').onclick=()=>$('#csv-dialog').showModal();
$('#upload-form').onsubmit=async e=>{e.preventDefault();const b=$('#upload-submit');b.disabled=true;b.textContent='正在解析与索引…';const form=new FormData();form.append('file',$('#doc-file').files[0]);form.append('kind',$('#doc-kind').value);form.append('scope',$('#doc-scope').value==='current'?(state.caseId==='DEMO-PIT-001'?'demo':state.caseId):'reference');try{const r=await api('/api/documents',{method:'POST',body:form});$('#upload-dialog').close();toast(`已入库 ${r.chunks} 个资料片段。`);await loadDocuments();}catch(err){toast(err.message);}finally{b.disabled=false;b.textContent='解析并入库';}};
$('#csv-form').onsubmit=async e=>{e.preventDefault();const b=$('#csv-submit');b.disabled=true;const form=new FormData();form.append('ground',$('#ground-file').files[0]);if($('#bottom-file').files[0])form.append('bottom',$('#bottom-file').files[0]);form.append('project_name',$('#csv-name').value);try{const r=await api('/api/cases/import',{method:'POST',body:form});$('#csv-dialog').close();newChat();await loadCases(r.id);toast('CSV 校验通过，已创建独立案例。');}catch(err){toast(err.message);}finally{b.disabled=false;}};
async function init(){try{const status=await api('/api/status');$('#provider-name').textContent=status.model_configured?status.model:'离线证据摘录可用';$('#provider-detail').textContent='本地混合检索 · '+status.chunks+' 个证据片段';if(!status.model_configured)$('#engine').value='offline';await Promise.all([loadCases(),loadDocuments(),loadHistory(),loadReports()]);}catch(e){toast('服务初始化失败：'+e.message);}}
init();
