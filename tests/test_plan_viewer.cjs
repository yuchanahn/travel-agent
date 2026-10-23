const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function node(tag,text,cls){return {tag,textContent:text??'',className:cls||'',children:[],checked:false,append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},addEventListener(){}};}
const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,node(id));return elements.get(id);};
const context=vm.createContext({node,$,safeLink:(label,url)=>({...node('a',label),href:url}),window:{confirm(){return false;}},setInterval(){},clearInterval(){}});
let source=fs.readFileSync('src/travel_agent/static/plan.js','utf8');
vm.runInContext(source.slice(0,source.indexOf("$('plan-open').addEventListener")),context);
vm.runInContext(`planRunId='a'.repeat(32);planData={revision:2,items:[
 {id:'1',kind:'activity',title:'<img onerror=alert(1)>',date:'2026-11-14',start:'11:00',confirmed:false},
 {id:'2',kind:'activity',title:'earlier',date:'2026-11-14',start:'10:00',confirmed:true},
 {id:'3',kind:'cost',title:'unknown',amount_won:null,confirmed:false},
 {id:'4',kind:'lodging',title:'stay',amount_won:200000,cost_status:'estimate',basis:'2명1박',confirmed:false}],
 budget:{item_count:2,observed_won:0,estimated_won:200000,unknown_count:1},confirmed_budget:{item_count:0,observed_won:0,estimated_won:0,unknown_count:0}};renderPlan();`,context);
const flatten=x=>[x.textContent,...x.children.flatMap(flatten)].join(' ');
assert.ok(flatten($('plan-content')).includes('<img onerror=alert(1)>'),'User input is literal text');
assert.ok(flatten($('plan-content')).includes('金額')===false);
assert.ok(flatten($('plan-content')).includes('금액 미확인'));
vm.runInContext("planView='timeline';renderPlan();",context);
assert.ok(flatten($('plan-content')).indexOf('earlier')<flatten($('plan-content')).indexOf('<img'));
vm.runInContext("planView='budget';renderPlan();",context);
assert.ok(flatten($('plan-content')).includes('200,000원'));
assert.ok(flatten($('plan-content')).includes('미확인 금액은0원이 아니며'));
$('plan-confirmed').checked=true;vm.runInContext("planView='summary';renderPlan();",context);
assert.ok(flatten($('plan-content')).includes('earlier'));
assert.ok(!flatten($('plan-content')).includes('stay'));
assert.ok($('plan-download').href.endsWith('confirmed=1'));
console.log('PASS: plan summary/timeline/budget, literal text, unknown costs and confirmed scope');
