// Local development browser test. Real Qwen responses; no DOM/data mocks.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:50733';
const output=path.resolve(process.env.BROWSER_TEST_OUTPUT||'data/private/095-browser');
const assets=path.resolve('docs/assets');
const queries=[
 '공개 합성 여행이야. 2026년 11월 14일부터 15일까지 성인 2명이 이천에서 자가용으로 갈 거야. 총예산은 25만원이고, 합성 정원 A 산책과 합성 숙소 B를 후보로 생각 중이야. 실제 장소를 검색하지 말고 지금 정한 조건만 간결하게 확인해줘.',
 '총예산만 20만원으로 바꿀게. 날짜와 인원, 이동수단은 그대로야. 조건만 간결하게 확인해줘.',
 '인원만 성인 3명으로 바꿀게. 총예산 20만원, 날짜와 이동수단은 그대로야. 검색하지 말고 조건만 간결하게 확인해줘.'
];
(async()=>{
 await fs.mkdir(output,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const created=[];const report={queries,turns:[],checks:{},browser:'isolated installed Chrome, real DOM',web_enabled:false};
 const save=()=>fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));
 async function json(url){const r=await page.request.get(base+url);assert.equal(r.status(),200);return r.json();}
 async function shot(selector,name){await page.locator(selector).screenshot({path:path.join(assets,name),animations:'disabled'});}
 try{
  await page.goto(base);await page.locator('#question').waitFor();
  await shot('.chat-shell','portfolio-095-home.png');
  await page.locator('#theme-toggle').click();
  await shot('.chat-shell','portfolio-095-home-light.png');
  await page.locator('#enable-web').uncheck();
  for(const query of queries){
   await page.locator('#question').fill(query);
   const post=page.waitForResponse(r=>r.url()===base+'/api/runs'&&r.request().method()==='POST');
   await page.locator('#send').click();const id=(await(await post).json()).id;created.push(id);
   let job;const deadline=Date.now()+410000;
   do{job=await json('/api/runs/'+id);if(['queued','running'].includes(job.state))await new Promise(r=>setTimeout(r,400));}while(['queued','running'].includes(job.state)&&Date.now()<deadline);
   report.turns.push({query,job,plan:await json('/api/plans/'+id)});await save();
   assert.equal(job.result?.status,'completed',JSON.stringify(job.result));
   assert.equal(job.result?.tool_calls,0,'Synthetic UI demo should have no tool calls');
   await page.locator('#send').waitFor({state:'visible'});
   await page.waitForFunction(()=>!document.querySelector('#send').disabled);
   console.log(JSON.stringify({turn:created.length,status:job.result.status,items:report.turns.at(-1).plan.items.length}));
  }
  const id=created.at(-1);let plan=await json('/api/plans/'+id);
  assert(plan.items.some(i=>i.title==='총예산'&&i.note.includes('20만원')));
  assert(plan.items.some(i=>i.title==='인원'&&i.note.includes('3명')));
  assert.equal(plan.items.length,6);
  await shot('.chat-shell','portfolio-095-chat.png');
  await page.locator('#plan-open').click();await page.locator('#plan-dialog[open]').waitFor();
  const activity=plan.items.find(i=>i.kind==='activity');assert(activity);
  const card=page.locator('#plan-content .plan-item').filter({has:page.getByRole('heading',{name:activity.title,exact:true})});
  await card.getByRole('button',{name:'수정',exact:true}).click();
  await page.locator('#plan-date').fill('2026-11-14');await page.locator('#plan-start').fill('10:00');await page.locator('#plan-end').fill('12:00');
  await page.locator('#plan-form button[type=submit]').click();
  await page.waitForFunction(()=>!document.querySelector('#plan-editor').open);
  await card.getByRole('button',{name:'선택 확정',exact:true}).click();
  await page.locator('#plan-confirmed').check();
  await shot('#plan-dialog','portfolio-095-plan-confirmed.png');
  await page.locator('#plan-confirmed').uncheck();
  // UI-only demo data: this price is a synthetic assumption, not a fetched quote.
  for(const item of [{title:'합성 숙박비 · 시연용 가정',amount:'150000',basis:'성인 3명 1박 · 실제 예약 아님'},{title:'식비 · 확인 필요',amount:'',basis:''}]){
   await page.locator('#plan-editor summary').click();await page.locator('#plan-kind').selectOption('cost');
   await page.locator('#plan-item-title').fill(item.title);await page.locator('#plan-amount').fill(item.amount);
   await page.locator('#plan-cost-status').selectOption(item.amount?'estimate':'unknown');await page.locator('#plan-basis').fill(item.basis);
   await page.locator('#plan-form button[type=submit]').click();await page.waitForFunction(()=>!document.querySelector('#plan-editor').open);
  }
  await shot('#plan-dialog','portfolio-095-plan-summary.png');
  await page.locator('[data-plan-view=timeline]').click();await shot('#plan-dialog','portfolio-095-plan-timeline.png');
  await page.locator('[data-plan-view=budget]').click();await shot('#plan-dialog','portfolio-095-plan-budget.png');
  const download=page.waitForEvent('download');await page.locator('#plan-download').click();await(await download).saveAs(path.join(output,'travel-plan.md'));
  const markdown=await fs.readFile(path.join(output,'travel-plan.md'),'utf8');assert(markdown.includes('150,000'));assert(markdown.includes('확인 필요'));
  await page.pdf({path:path.join(output,'travel-plan-budget.pdf'),format:'A4',printBackground:true});
  plan=await json('/api/plans/'+id);assert.equal(plan.budget.estimated_won,150000);assert.equal(plan.budget.unknown_count,1);
  report.final_plan=plan;
  await page.locator('#plan-close').click();await page.locator('#compare-open').click();
  await page.locator('#compare-left').selectOption(created[0]);await page.locator('#compare-right').selectOption(created[1]);
  await page.locator('#compare-run').click();await page.locator('#compare-output table').waitFor();
  await shot('#compare-dialog','portfolio-095-comparison.png');await page.locator('#compare-close').click();
  await page.setViewportSize({width:390,height:844});await page.locator('#plan-open').click();await page.locator('[data-plan-view=budget]').click();
  report.checks.mobile_overflow=await page.locator('#plan-dialog').evaluate(e=>e.scrollWidth>e.clientWidth+1);
  assert.equal(report.checks.mobile_overflow,false);await page.locator('#plan-dialog').screenshot({path:path.join(output,'mobile-budget.png')});
  report.checks={...report.checks,three_turns:true,budget_correction:true,people_correction:true,manual_time_edit:true,user_confirmation:true,unknown_cost:true,markdown_download:true,pdf_rendered:true,comparison:true};
 }finally{
  await save();
  if(created.length){
   const executions=await json('/api/executions');const descendants=new Set([created[0]]);let changed=true;
   while(changed){changed=false;for(const r of executions.runs)if(descendants.has(r.parent_id)&&!descendants.has(r.id)){descendants.add(r.id);changed=true;}}
   assert([...descendants].every(id=>created.includes(id)),'Unexpected user turn: preserve root');
   for(const id of created){await fs.cp(path.resolve('data/private/web-host',id),path.join(output,'evidence',id),{recursive:true});}
   const deleted=await page.request.delete(base+'/api/conversations/'+created[0]);assert.equal(deleted.status(),200);report.cleanup=await deleted.json();
   report.checks.deleted_root_404=(await page.request.get(base+'/api/runs/'+created[0])).status()===404;assert(report.checks.deleted_root_404);
  }
  await save();await browser.close();
 }
 console.log(JSON.stringify(report.checks));
})().catch(e=>{console.error(e);process.exitCode=1;});
