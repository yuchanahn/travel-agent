const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/travel_agent/static/comparison.js','utf8');
function node(tag,text){return {tag,textContent:text??'',children:[],append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=xs;}};}
const area=node('div'),context=vm.createContext({$:()=>area,node,JSON});
vm.runInContext(source.slice(source.indexOf('function renderComparison'),source.indexOf('async function openComparison')),context);
context.left={query:'<script>same</script>',execution_config:{model:'qwen'},input_fingerprint:'a',execution_summary:{prompt_tokens:{reported_sum:null,complete:false},output_tokens:{reported_sum:12,complete:false},errors_by_type:{duplicate_rejected:3}}};
context.right={query:'<script>same</script>',execution_config:{model:'qwen'},input_fingerprint:'b',execution_summary:{prompt_tokens:{reported_sum:0,complete:true},output_tokens:{reported_sum:20,complete:true}}};
vm.runInContext('renderComparison(left,right)',context);
assert.ok(area.children[0].textContent.includes('입력: 다름'));
function flatten(x){return [x.textContent,...x.children.flatMap(flatten)].join(' ');}
const text=flatten(area);
assert.ok(text.includes('미수집'));
assert.ok(text.includes('12 (일부)'));
assert.ok(text.includes('<script>same</script>'),'Query stays text rather than HTML');
assert.ok(text.includes('답변 정확도는 별도'));
console.log('PASS: comparison distinguishes input changes and missing/partial tokens');
