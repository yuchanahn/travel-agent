'use strict';
const PLAN_KINDS={activity:'일정',lodging:'숙소',cost:'비용',transport:'교통',note:'메모·조건'};
let planRunId=null,planData=null,planView='summary',planEditId=null,planEditRevision=null,planPoll=null;
const planIds={title:'plan-item-title',date:'plan-date',start:'plan-start',end:'plan-end',place:'plan-place',address:'plan-address',basis:'plan-basis',source_url:'plan-source',note:'plan-note'};
function planMessage(message){$('plan-message').textContent=message;}
function planItems(){return (planData?.items||[]).filter(i=>!$('plan-confirmed').checked||i.confirmed);}
function planSort(items){return [...items].sort((a,b)=>((a.date||'9999')+' '+(a.start||'99:99')).localeCompare((b.date||'9999')+' '+(b.start||'99:99')));}
function planMoney(item){return item.amount_won===null||item.amount_won===undefined?'금액 미확인':item.amount_won.toLocaleString('ko-KR')+'원';}
function planCostStatus(item){return {unknown:'미확인',estimate:'예상',observed:'조회 금액'}[item.cost_status]||'미확인';}
function planWhen(item){return [item.date||'날짜 미정',item.start||'시간 미정',item.end?'– '+item.end:''].filter(Boolean).join(' ');}
function planCard(item){
  const card=node('article',undefined,'plan-item'),head=node('div',undefined,'plan-item-head');
  head.append(node('span',item.confirmed?'선택 확정':'초안','plan-badge'+(item.confirmed?' confirmed':'')),node('span',PLAN_KINDS[item.kind]));card.append(head,node('h3',item.title));
  if(item.kind!=='cost')card.append(node('p',planWhen(item),'plan-when'));
  if(item.place)card.append(node('p',item.place,'plan-place'));
  if(item.address)card.append(node('p',item.address));
  if(item.kind==='cost'||item.amount_won!==undefined&&item.amount_won!==null)card.append(node('strong',planMoney(item),'plan-price'),node('p',planCostStatus(item)+' · '+(item.basis||'적용 기준 미정')));
  if(item.note)card.append(node('p',item.note));
  if(item.source_url)card.append(safeLink('출처 열기 ↗',item.source_url,'plan-source'));
  const actions=node('div',undefined,'plan-item-actions');
  for(const [label,act] of [[item.confirmed?'확정 해제':'선택 확정',()=>changePlan({action:'confirm',id:item.id,confirmed:!item.confirmed})],['수정',()=>editPlanItem(item)],['삭제',()=>{if(window.confirm('이 계획 항목을 삭제할까요?'))changePlan({action:'delete',id:item.id});}]]){
    const button=node('button',label);button.type='button';button.addEventListener('click',act);actions.append(button);
  }
  card.append(actions);return card;
}
function renderPlan(){
  const content=$('plan-content');content.replaceChildren();if(!planData)return;
  const items=planItems();
  $('plan-download').href='/api/plans/'+planRunId+'/markdown?confirmed='+Number($('plan-confirmed').checked);
  if(!items.length){content.append(node('div',$('plan-confirmed').checked?'아직 선택 확정한 항목이 없어요. 전체 계획에서 항목을 골라주세요.':'계획이 아직 비어 있어요. 대화에서 계획 기록을 요청하거나 아래에서 직접 추가해보세요.','plan-empty'));return;}
  if(planView==='budget'){
    const b=$('plan-confirmed').checked?planData.confirmed_budget:planData.budget,stats=node('div',undefined,'plan-budget-stats');
    for(const [label,value] of [['조회 금액 합계',b.item_count?b.observed_won.toLocaleString()+'원':'—'],['예상 금액 합계',b.item_count?b.estimated_won.toLocaleString()+'원':'—'],['금액 미확인',b.unknown_count+'개']]){const stat=node('div');stat.append(node('span',label),node('strong',value));stats.append(stat);}
    content.append(stats,node('p','입력한 비용 항목만 합산합니다. 미확인 금액은0원이 아니며 전체 여행 비용과 다를 수 있습니다.','plan-muted'));
    const grid=node('div',undefined,'plan-grid');for(const item of items.filter(i=>i.kind==='cost'||i.amount_won!==undefined&&i.amount_won!==null))grid.append(planCard(item));content.append(grid);return;
  }
  if(planView==='timeline'){
    const entries=planSort(items.filter(i=>['activity','transport','lodging'].includes(i.kind)));
    if(!entries.length){content.append(node('p','일정·숙소·교통 항목을 추가하면 시간표로 볼 수 있어요.','plan-empty'));return;}
    let current=null;for(const item of entries){const day=item.date||'날짜 미정';if(day!==current){content.append(node('h3',day,'plan-day'));current=day;}const row=node('div',undefined,'plan-timeline-row');row.append(node('div',item.start||'미정','plan-time'),planCard(item));content.append(row);}return;
  }
  for(const [kind,label] of Object.entries(PLAN_KINDS)){const list=items.filter(i=>i.kind===kind);if(!list.length)continue;content.append(node('h3',label+' · '+list.length,'plan-section-title'));const grid=node('div',undefined,'plan-grid');for(const item of planSort(list))grid.append(planCard(item));content.append(grid);}
}
async function refreshPlan(){
  if(!planRunId)return;
  try{const id=planRunId,value=await api('/api/plans/'+id);if(id!==planRunId)return;planData=value;renderPlan();planMessage(value.items.length+'개 항목 · '+value.items.filter(i=>i.confirmed).length+'개 선택 확정');}
  catch(exc){planMessage(exc.message);}
}
async function changePlan(payload,revision=planData?.revision){
  if(!planRunId)return;
  try{await api('/api/plans/'+planRunId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,...payload})});await refreshPlan();return true;}
  catch(exc){planMessage(exc.message);return false;}
}
function resetPlanEditor(){planEditId=null;planEditRevision=null;$('plan-form').reset();$('plan-cost-fields').hidden=true;}
function editPlanItem(item){
  resetPlanEditor();planEditId=item.id;planEditRevision=planData.revision;
  $('plan-kind').value=item.kind;for(const [key,id]of Object.entries(planIds))$(id).value=item[key]||'';
  $('plan-amount').value=item.amount_won??'';$('plan-cost-status').value=item.cost_status||'unknown';$('plan-cost-fields').hidden=item.kind==='note';$('plan-editor').open=true;$('plan-item-title').focus();
}
$('plan-open').addEventListener('click',async()=>{
  planRunId=activeId;planData=null;resetPlanEditor();$('plan-content').replaceChildren();$('plan-editor').open=false;$('plan-editor').hidden=!planRunId;$('plan-download').hidden=!planRunId;$('plan-print').disabled=!planRunId;
  $('plan-dialog').showModal();clearInterval(planPoll);
  if(!planRunId){planMessage('먼저 대화를 시작하면 이곳에 여행 계획을 모을 수 있어요.');return;}
  await refreshPlan();planPoll=setInterval(refreshPlan,3000);
});
$('plan-dialog').addEventListener('close',()=>clearInterval(planPoll));
$('plan-close').addEventListener('click',()=>$('plan-dialog').close());
$('plan-refresh').addEventListener('click',refreshPlan);
$('plan-confirmed').addEventListener('change',renderPlan);
for(const button of document.querySelectorAll('[data-plan-view]'))button.addEventListener('click',()=>{planView=button.dataset.planView;for(const b of document.querySelectorAll('[data-plan-view]'))b.setAttribute('aria-pressed',String(b===button));renderPlan();});
$('plan-kind').addEventListener('change',()=>{$('plan-cost-fields').hidden=$('plan-kind').value==='note';});
$('plan-cancel-edit').addEventListener('click',resetPlanEditor);
$('plan-form').addEventListener('submit',async event=>{
  event.preventDefault();const item={kind:$('plan-kind').value};for(const [key,id] of Object.entries(planIds))item[key]=$(id).value;
  if(planEditId)item.id=planEditId;
  if(item.kind!=='note'){item.amount_won=$('plan-amount').value===''?null:Number($('plan-amount').value);item.cost_status=$('plan-cost-status').value;}
  else{item.amount_won=null;item.cost_status='unknown';}
  if(await changePlan({action:'upsert',items:[item]},planEditRevision??planData?.revision)){resetPlanEditor();$('plan-editor').open=false;}
});
$('plan-print').addEventListener('click',()=>window.print());
