'use strict';
function renderComparison(left,right){
  const area=$('compare-output');area.replaceChildren();
  const keys=['model','provider','options','limits','completion_protocol','enable_web','mode'];
  const known=keys.every(k=>left.execution_config?.[k]!==undefined&&left.execution_config?.[k]!==null&&right.execution_config?.[k]!==undefined&&right.execution_config?.[k]!==null);
  const sameConfig=known&&JSON.stringify(left.execution_config)===JSON.stringify(right.execution_config);
  const sameInput=left.input_fingerprint&&right.input_fingerprint&&left.input_fingerprint===right.input_fingerprint;
  area.append(node('p','질문: '+(left.query===right.query?'동일':'다름')+' · 설정: '+(!known?'미수집':sameConfig?'동일':'다름')+' · 최초 모델 입력: '+(!left.input_fingerprint||!right.input_fingerprint?'미수집':sameInput?'동일':'다름')));
  area.append(node('p','실행 완료와 답변 정확도는 별도입니다. 이후 도구 결과와 검색 시점도 다를 수 있습니다.'));
  const table=node('table'),head=node('tr');head.append(node('th','항목'),node('th','A'),node('th','B'));table.append(head);
  const usage=(s,k)=>s?.[k]?.reported_sum===null||s?.[k]?.reported_sum===undefined?'미수집':s[k].reported_sum+(s[k].complete?'':' (일부)');
  const fields=[['질문',j=>j.query],['모델',j=>j.execution_config?.model??'미수집'],['종료',j=>j.execution_summary?.status??j.state],['시간(초)',j=>j.execution_summary?.elapsed_seconds],['모델 요청',j=>j.execution_summary?.model_requests],['도구 요청',j=>j.execution_summary?.tool_requests],['도구 오류',j=>j.execution_summary?.tool_errors],['중복 거절',j=>j.execution_summary?.errors_by_type?.duplicate_rejected??0],['자동 HTTP',j=>j.execution_summary?.automatic_http_observations],['입력 토큰',j=>usage(j.execution_summary,'prompt_tokens')],['출력 토큰',j=>usage(j.execution_summary,'output_tokens')]];
  for(const [label,get] of fields){const row=node('tr');row.append(node('th',label),node('td',String(get(left)??'미수집')),node('td',String(get(right)??'미수집')));table.append(row);}
  const wrap=node('div',undefined,'table-wrap');wrap.append(table);area.append(wrap);
}
async function openComparison(){
  $('compare-output').replaceChildren();$('compare-dialog').showModal();
  try{const {runs}=await api('/api/executions');for(const side of ['left','right']){const select=$('compare-'+side);select.replaceChildren();for(const run of runs){const option=node('option',(run.query||'질문 없음').slice(0,65)+' · '+run.created_at+' · '+run.id.slice(0,6));option.value=run.id;select.append(option);}}if(runs.length>1)$('compare-right').selectedIndex=1;$('compare-run').disabled=runs.length<2;if(runs.length<2)$('compare-output').append(node('p','비교하려면 저장된 실행이 두 개 이상 필요합니다.'));}
  catch(exc){$('compare-output').append(node('p',exc.message));}
}
async function compareSelected(){
  const a=$('compare-left').value,b=$('compare-right').value;
  if(a===b){$('compare-output').replaceChildren(node('p','서로 다른 실행을 선택해주세요.'));return;}
  try{const jobs=await Promise.all([a,b].map(id=>api('/api/runs/'+id+'?after=2147483647')));renderComparison(...jobs);}
  catch(exc){$('compare-output').replaceChildren(node('p',exc.message));}
}
$('compare-open').addEventListener('click',openComparison);
$('compare-close').addEventListener('click',()=>$('compare-dialog').close());
$('compare-run').addEventListener('click',compareSelected);
