'use strict';
const coach = {context:null, history:[], controller:null, ready:false};
function coachButton(kind,id,label='问 AI 教练') {
  return `<button class="outline-button" data-action="ask-coach" data-kind="${kind}" data-id="${id}">✧ ${label}</button>`;
}
async function openCoach(kind='general',id='') {
  const context={kind,entry_id:id||null,star:state.studyStar||1};
  if(JSON.stringify(context)!==JSON.stringify(coach.context)) {
    coach.history=[];$('#coach-messages').replaceChildren();
  }
  coach.context=context;
  const name=kind==='general'?'棋子 · 装备 · 阵容':state.data[kind].find(x=>x.id===id)?.name||'当前资料';
  $('#coach-context').textContent=name+(kind==='heroes'?` · ${context.star} 星`:'');
  $('#coach-dialog').showModal();
  $('#coach-question').focus();coach.ready=false;$('#coach-submit').disabled=true;
  $('#coach-status').textContent='正在检查 AI 服务…';
  try {
    const r=await fetch('/api/v1/ai/status',{signal:AbortSignal.timeout(8000)});
    if(!r.ok)throw Error('无法检查 AI 服务，请稍后重新打开。');
    const info=await r.json();coach.ready=info.configured;
    $('#coach-status').textContent=info.message;
    $('#coach-access-field').hidden=!info.access_required;
    $('#coach-submit').disabled=!coach.ready;
  } catch(e) {$('#coach-status').textContent=e.message;}
  const questions=kind==='heroes'?['这个棋子的技能与出装应该怎么理解？','这个棋子的装备有哪些替代思路？']:kind==='items'?['这件装备适合哪些棋子，为什么？','这件装备的适用条件和局限是什么？']:kind==='lineups'?['这套阵容什么时候适合选？','装备怎么分配，缺少核心时怎么过渡？']:['怎样判断应该搜牌还是升级？','如何判断装备应该优先给前排还是主C？'];
  $('#coach-prompts').innerHTML=questions.map(q=>`<button type="button" class="filter-chip" data-coach-prompt="${esc(q)}">${esc(q)}</button>`).join('');
}
function coachMessage(role,text) {
  const article=document.createElement('article');article.className='coach-message '+role;
  const label=document.createElement('strong');label.textContent=role==='user'?'你':'AI 教练';
  const body=document.createElement('p');body.textContent=text;
  article.append(label,body);$('#coach-messages').append(article);
  return article;
}
document.addEventListener('click',e=>{
  const button=e.target.closest('[data-action="ask-coach"]');
  if(button&&state.data)openCoach(button.dataset.kind,button.dataset.id);
  const prompt=e.target.closest('[data-coach-prompt]');
  if(prompt){$('#coach-question').value=prompt.dataset.coachPrompt;$('#coach-question').focus();}
});
$('#coach-close').addEventListener('click',()=>$('#coach-dialog').close());
$('#coach-dialog').addEventListener('close',()=>{coach.controller?.abort();});
$('#coach-form').addEventListener('submit',async e=>{
  e.preventDefault();const question=$('#coach-question').value.trim();
  if(!question||!coach.ready||coach.controller)return;
  const controller=new AbortController();coach.controller=controller;
  $('#coach-submit').disabled=true;$('#coach-question').disabled=true;
  const userMessage=coachMessage('user',question);$('#coach-status').textContent='正在结合资料分析…';
  const timeout=setTimeout(()=>controller.abort(),60000);
  try {
    const response=await fetch('/api/v1/ai/ask',{method:'POST',headers:{'Content-Type':'application/json','X-AI-Access-Token':$('#coach-access').value},body:JSON.stringify({...coach.context,question,history:coach.history.slice(-8)}),signal:controller.signal});
    const result=await response.json();
    if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'问题未能提交，请检查内容后重试。');
    const message=coachMessage('assistant',result.answer);
    if(result.sources?.length){
      const caption=document.createElement('small');caption.textContent='本次检索资料（供核对）：';message.append(caption);
      const links=document.createElement('div');links.className='trait-list';
      result.sources.slice(0,12).forEach(source=>{
        const link=document.createElement('a');link.textContent=source.name;link.className='trait-button';
        link.href=source.kind==='heroes'?`#hero/${source.id}`:source.kind==='lineups'?`#lineup/${source.id}`:'#items';
        link.addEventListener('click',e=>{e.preventDefault();$('#coach-dialog').close();if(source.kind==='heroes')showHero(source.id);else if(source.kind==='lineups')showLineup(source.id);else showItem(source.id);});links.append(link);
      });message.append(links);
    }
    coach.history.push({role:'user',content:question},{role:'assistant',content:result.answer.slice(0,6000)});
    coach.history=coach.history.slice(-8);$('#coach-question').value='';
    $('#coach-status').textContent=result.note+' · 快照 '+result.version;
    message.scrollIntoView({block:'nearest'});
  } catch(error) {
    userMessage.remove();
    $('#coach-status').textContent=error.name==='AbortError'?'请求已取消或超时，问题已保留，可重新发送。':error.message;
  } finally {
    clearTimeout(timeout);coach.controller=null;$('#coach-submit').disabled=!coach.ready;$('#coach-question').disabled=false;
    if($('#coach-dialog').open)$('#coach-question').focus();
  }
});
