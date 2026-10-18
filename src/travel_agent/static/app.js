'use strict';
const $ = id => document.getElementById(id);
const labels = {queued:'대기 중',running:'실행 중',done:'응답 완료',error:'실행 오류',interrupted:'중단됨'};
const toolNames = {web_search:'웹 검색',web_read:'출처 본문 읽기',memory_search:'과거 기록 검색',memory_show:'과거 원문 읽기'};
let activeId = null, sequence = 0, timer = null, startedAt = null, finishedAt = null, answerText = '', pollTimer = null;
let eventCount = 0, toolCards = new Map(), sources = new Map();

function node(tag, text, className) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(className)n.className=className; return n; }
function safeLink(label,url,className) { try { const parsed=new URL(url); if(!['http:','https:'].includes(parsed.protocol))return node('span',label); const a=node('a',label,className);a.href=parsed.href;a.target='_blank';a.rel='noreferrer noopener';return a; } catch { return node('span',label); } }
function inline(parent,text) {
  const regex=/\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(\[web:[a-f0-9]+\])/g;
  let end=0, match;
  function plain(value){const pieces=value.split(/<br\s*\/?>/i);pieces.forEach((piece,i)=>{if(i)parent.append(document.createElement('br'));parent.append(document.createTextNode(piece));});}
  while((match=regex.exec(text))){plain(text.slice(end,match.index));if(match[1])parent.append(node('strong',match[1]));else if(match[2])parent.append(node('code',match[2]));else if(match[3])parent.append(safeLink(match[3],match[4]));else{const id=match[5].slice(1,-1);const source=sources.get(id);parent.append(source?safeLink(match[5],source.url,'citation'):node('span',match[5],'citation'));}end=regex.lastIndex;}
  plain(text.slice(end));
}
function markdown(element,text) {
  element.replaceChildren(); const lines=text.split('\n');let index=0;
  const isDivider=line=>/^\s*\|?\s*:?-{2,}:?\s*\|[\s|:\-]*$/.test(line);
  const cells=line=>line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(c=>c.trim());
  while(index<lines.length){const line=lines[index];
    if(!line.trim()){index++;continue;}
    if(line.trim().startsWith('```')){const code=[];index++;while(index<lines.length&&!lines[index].trim().startsWith('```'))code.push(lines[index++]);const pre=node('pre');pre.append(node('code',code.join('\n')));element.append(pre);index++;continue;}
    if(index+1<lines.length&&line.includes('|')&&isDivider(lines[index+1])){const wrap=node('div',undefined,'table-wrap'),table=node('table'),head=node('thead'),row=node('tr');for(const cell of cells(line)){const th=node('th');inline(th,cell);row.append(th);}head.append(row);table.append(head);const body=node('tbody');index+=2;while(index<lines.length&&lines[index].includes('|')&&lines[index].trim()){const tr=node('tr');for(const cell of cells(lines[index++])){const td=node('td');inline(td,cell);tr.append(td);}body.append(tr);}table.append(body);wrap.append(table);element.append(wrap);continue;}
    const heading=line.match(/^(#{1,4})\s+(.+)$/);if(heading){const h=node('h'+Math.min(heading[1].length+1,4));inline(h,heading[2]);element.append(h);index++;continue;}
    if(/^\s*([-*]|\d+\.)\s+/.test(line)){const ordered=/^\s*\d+\./.test(line),list=node(ordered?'ol':'ul');while(index<lines.length&&/^\s*([-*]|\d+\.)\s+/.test(lines[index])){const li=node('li');inline(li,lines[index++].replace(/^\s*([-*]|\d+\.)\s+/,''));list.append(li);}element.append(list);continue;}
    if(/^\s*---+\s*$/.test(line)){element.append(document.createElement('hr'));index++;continue;}
    const p=node('p');inline(p,line);element.append(p);index++;
  }
}
async function api(path,options={}){const response=await fetch(path,{...options,cache:'no-store'});const value=await response.json();if(!response.ok)throw new Error(value.error||'요청을 처리하지 못했습니다.');return value;}
function error(text){$('form-error').textContent=text;$('form-error').hidden=!text;}
function setState(state){$('state').textContent=labels[state]||state;$('state').className='state '+state;$('send').disabled=['queued','running'].includes(state);}
function updateClock(){if(!startedAt)return;const end=finishedAt?new Date(finishedAt).getTime():Date.now();const seconds=Math.max(0,Math.floor((end-new Date(startedAt).getTime())/1000));$('elapsed').textContent=Math.floor(seconds/60)+'분 '+String(seconds%60).padStart(2,'0')+'초';}
function reset(){startedAt=null;finishedAt=null;sequence=0;eventCount=0;toolCards=new Map();sources=new Map();answerText='';$('events').replaceChildren();$('answer').replaceChildren();$('source-list').replaceChildren();$('metrics').replaceChildren();$('event-count').textContent='0';$('copy').hidden=true;$('sources').hidden=true;$('metrics').hidden=true;$('answer-note').hidden=true;$('empty-state').hidden=true;$('run-content').hidden=false;$('trace-panel').hidden=false;$('progress').hidden=false;$('progress-text').textContent='실행 준비 중';clearInterval(timer);clearTimeout(pollTimer);timer=setInterval(updateClock,1000);}
function logCard(title,event){eventCount++;$('event-count').textContent=String(eventCount);const details=node('details',undefined,'log-item'),summary=node('summary'),dot=node('span',undefined,'log-dot'),name=node('span',title),time=node('span',new Date(event.timestamp).toLocaleTimeString('ko-KR',{hour12:false}),'log-time'),body=node('div',undefined,'log-detail');summary.append(dot,name,time);details.append(summary,body);$('events').append(details);return {details,body,dot,name};}
function showJson(parent,title,value){parent.append(node('h4',title),node('pre',JSON.stringify(value,null,2)));}
function addEvent(event){
  if(event.kind==='model_start'){$('progress-text').textContent='모델이 다음 행동을 선택하는 중';return;}
  if(event.kind==='model_end'){if(event.content){const card=logCard('모델 응답 · 중간 기록',event);card.dot.classList.add('done');const text=node('div',undefined,'prose');markdown(text,event.content);card.body.append(text);}return;}
  if(event.kind==='model_error'){const card=logCard('모델 호출 오류',event);card.dot.classList.add('error');card.body.append(node('p',event.error||event.error_type||'모델 응답 오류'));return;}
  if(event.kind==='tool_start'){const title=toolNames[event.name]||event.name;const card=logCard(title+' · 요청',event);showJson(card.body,'실제 인자',event.arguments);if(event.tool_call_id)card.body.append(node('small','호출 ID: '+event.tool_call_id));toolCards.set(event.span,card);$('progress-text').textContent=title+' 중';return;}
  if(event.kind==='tool_end'||event.kind==='tool_error'){const card=toolCards.get(event.span)||logCard(toolNames[event.name]||event.name,event);const failed=event.kind==='tool_error';card.dot.classList.add(failed?'error':'done');card.name.textContent=(toolNames[event.name]||event.name)+(failed?' · 오류':' · 결과 수신');showJson(card.body,'실제 반환 결과',event.result);if(event.elapsed_seconds!==undefined)card.body.append(node('small','실행 '+event.elapsed_seconds.toFixed(2)+'초'));return;}
  if(event.kind==='evidence_review'||event.kind==='citation_repair'){const card=logCard(event.kind==='evidence_review'?'근거 추가 검토':'인용 형식 재검토',event);card.body.append(node('p',event.feedback||''));return;}
  const card=logCard('실행 예산에 따른 마무리',event);showJson(card.body,'실행 상태',event);
}
function finish(job){clearInterval(timer);updateClock();$('progress').hidden=true;
  if(job.state==='error'||job.state==='interrupted'){answerText=job.error||'실행이 중단됐습니다.';$('answer').append(node('p',answerText));return;}
  const result=job.result||{};sources=new Map((result.web_sources||[]).map(source=>[source.id,source]));answerText=result.answer||result.partial_answer||(result.error?'모델 실행 오류: '+result.error:'최종 답변을 생성하지 못했습니다.');markdown($('answer'),answerText);$('copy').hidden=false;$('answer-note').hidden=false;
  if(result.status!=='completed'){$('state').textContent={output_limit:'출력 한도 도달',step_limit:'모델 호출 한도 도달',tool_limit:'도구 호출 한도 도달',timeout:'시간 한도 도달',model_error:'모델 응답 오류',protocol_error:'도구 형식 오류',context_limit:'입력 한도 도달'}[result.status]||result.status;$('state').className='state error';}
  const stats=[['모델 호출',result.model_calls],['도구 호출',result.tool_calls],['입력 토큰 합계',result.prompt_tokens],['출력 토큰 합계',result.output_tokens],['인용 ID',result.citation_status||'없음']];for(const [label,value] of stats){const item=node('span',label);item.append(node('strong',value??'—'));$('metrics').append(item);}$('metrics').hidden=false;
  if(sources.size){$('source-title').textContent='검색한 출처 '+sources.size+'개';$('sources').hidden=false;for(const source of sources.values()){const a=safeLink('',source.url,'source-link');a.append(node('strong',source.title),node('small',(source.page_fetched?'본문 읽기':'검색 요약')+(source.cited?' · 답변에서 인용':'')+' · '+source.id));$('source-list').append(a);}}
}
async function poll(id){if(id!==activeId)return;try{const job=await api('/api/runs/'+id+'?after='+sequence);if(id!==activeId)return;sequence=job.next_sequence;startedAt=job.started_at||job.created_at;finishedAt=job.finished_at||null;$('asked-text').textContent=job.query;setState(job.state);for(const event of job.events)addEvent(event);updateClock();if(['done','error','interrupted'].includes(job.state)){finish(job);await history();}else{pollTimer=setTimeout(()=>poll(id),1100);}}catch(exc){if(id!==activeId)return;clearInterval(timer);$('progress-text').textContent='연결을 확인해주세요. 실행 기록을 다시 선택하면 이어서 볼 수 있습니다.';error(exc.message);$('send').disabled=false;}}
async function openRun(id){activeId=id;localStorage.setItem('travel-agent-last-run',id);reset();await poll(id);}
async function history(){try{const {runs}=await api('/api/runs');$('run-count').textContent=String(runs.length);$('history').replaceChildren();if(!runs.length)$('history').append(node('p','아직 실행 기록이 없습니다.','muted small'));for(const run of runs.slice(0,8)){const button=node('button',undefined,'history-item'+(run.id===activeId?' active':''));button.type='button';button.append(node('strong',run.query),node('span',(labels[run.state]||run.state)+' · '+new Date(run.created_at).toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})));button.addEventListener('click',()=>openRun(run.id));$('history').append(button);}}catch{/* Current run can still complete if history refresh fails. */}}
async function health(){try{const status=await api('/api/health');const ready=status.ollama.connected&&status.ollama.model_installed;$('connection').textContent=ready?'로컬 모델 연결됨':'로컬 모델 연결 확인 필요';$('connection').className='connection'+(ready?'':' offline');$('model-name').textContent=status.model;$('model-options').textContent='컨텍스트 '+status.options.num_ctx.toLocaleString()+' · 출력 상한 '+status.options.num_predict.toLocaleString();if(!status.brave_configured){$('connection').textContent=ready?'모델 연결됨 · Brave 키 없음':'모델 연결 및 Brave 키 확인 필요';$('connection').classList.add('offline');}}catch{$('connection').textContent='서버 연결 확인 필요';$('connection').className='connection offline';}}
$('question').addEventListener('input',()=>$('char-count').textContent=$('question').value.length.toLocaleString()+' / 4,000');
$('question').addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();if(!$('send').disabled)$('question-form').requestSubmit();}});
$('question-form').addEventListener('submit',async event=>{event.preventDefault();error('');$('send').disabled=true;try{const {id}=await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:$('question').value,enable_web:$('enable-web').checked})});await openRun(id);await history();}catch(exc){error(exc.message);$('send').disabled=false;}});
$('copy').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(answerText);$('copy').textContent='복사됨';setTimeout(()=>$('copy').textContent='답변 복사',1500);}catch{error('브라우저에서 복사를 허용해주세요.');}});
const presets=[['비 오는 날 · 커플 당일치기','서울에서 대중교통으로 당일치기 갈 만한 커플 여행지 두 곳을 비교해줘. 비가 와도 할 일이 있으면 좋겠어. 교통과 실내 대안의 근거를 보여줘.'],['춘천 · 25만원 · 차 없이','차 없이 춘천으로 커플 1박2일 여행을 생각 중이야. 두 사람이 총25만원 예산일 때 박물관과 케이블카를 비교해줘. 교통·비 오는 날 대안과 확인하지 못한 비용을 구분해줘.'],['강릉 · 부모님 · 실내 여행','부모님과 강릉에 주말 당일치기로 가려고 해. 비가 오고 오래 걷기 어렵다고 할 때 실내 여행지 두 곳을 비교하고 이동·관람 제약을 확인해줘.']];
for(const [label,question]of presets){const button=node('button',label,'preset');button.type='button';button.addEventListener('click',()=>{$('question').value=question;$('question').dispatchEvent(new Event('input'));$('question').focus();});$('presets').append(button);}
health();history();setInterval(health,30000);const last=localStorage.getItem('travel-agent-last-run');if(last&&/^[a-f0-9]{32}$/.test(last))openRun(last);
