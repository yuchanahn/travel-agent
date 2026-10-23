const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('src/travel_agent/static/app.js','utf8');
function node(tag,text){return {tag,textContent:text??'',children:[],append(...x){this.children.push(...x);},className:''};}
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,node(id));return elements.get(id);}
const context=vm.createContext({$:element,node,clearInterval(){},timer:null,updateClock(){},markdown(){},Map,
 job:{state:'done',result:{status:'completed',answer:'ok',prompt_tokens:0,output_tokens:0},execution_summary:{
 tool_successes:9,tool_errors:4,errors_by_type:{duplicate_rejected:3},stored_document_reads:1,
 automatic_http_observations:6,prompt_tokens:{reported_sum:null,complete:false},output_tokens:{reported_sum:12,complete:false}}}});
vm.runInContext(source.slice(source.indexOf('function finish(job)'),source.indexOf('async function poll(')),context);
vm.runInContext('finish(job)',context);
const cards=element('metrics').children;
function value(label){return cards.find(x=>x.textContent===label)?.children[0]?.textContent;}
assert.equal(value('입력 토큰 합계'),'—','Missing tokens must not become zero');
assert.equal(value('도구 성공'),9);
assert.equal(value('도구 오류'),4);
assert.equal(value('중복 거절'),3);
assert.equal(value('자동 HTTP 수집'),6);
assert.ok(cards.some(x=>x.textContent.includes('미수집')));
console.log('PASS: real finish handler renders separate counters and incomplete usage');
