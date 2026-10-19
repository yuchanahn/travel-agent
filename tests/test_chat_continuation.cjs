// Exercise the actual browser handlers without network or a DOM dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/travel_agent/static/app.js', 'utf8');
const elements = new Map(), handlers = new Map(), posts = [];
function element(id) {
  if (!elements.has(id)) elements.set(id, {value:'followup',style:{},replaceChildren(){},
    focus(){},dispatchEvent(){},addEventListener(type, callback){handlers.set(id+':'+type, callback);}});
  return elements.get(id);
}
const context = vm.createContext({$:element,activeId:'parent',parentId:null,renderedConversation:'',
  labels:{done:'done'},clearTimeout(){},clearInterval(){},pollTimer:null,timer:null,
  localStorage:{removeItem(){}},error(){},Event:class{},
  async api(path, options){posts.push(JSON.parse(options.body));return {id:'child'};},
  async openRun(){},async history(){}});
function load(start, end) {vm.runInContext(source.slice(source.indexOf(start), source.indexOf(end)), context);}
load('function showConversation(', '\nfunction node(');
load('function setState(', '\nfunction updateClock(');
load("$('question-form').addEventListener('submit'", "$('copy').addEventListener");
load("$('new-chat').addEventListener", "$('toggle-sidebar').addEventListener");
(async () => {
  const job={id:'parent',state:'done',result:{status:'tool_limit'},conversation:[],can_continue:true};
  context.job=job;
  vm.runInContext("showConversation(job);setState(job.state)",context);
  assert.equal(context.parentId,'parent');
  assert.equal(element('send').disabled,false);
  await handlers.get('question-form:submit')({preventDefault(){}});
  assert.equal(posts[0].parent_id,'parent');
  job.can_continue=false;
  vm.runInContext("showConversation(job);setState(job.state)",context);
  assert.equal(element('send').disabled,true);
  await handlers.get('question-form:submit')({preventDefault(){}});
  assert.equal(posts.length,1,'Missing context must never silently create a new chat');
  handlers.get('new-chat:click')();
  assert.equal(context.activeId,null);
  assert.equal(element('send').disabled,false);
  await handlers.get('question-form:submit')({preventDefault(){}});
  assert.equal(posts[1].parent_id,null,'Only explicit new-chat detaches the parent');
  console.log('PASS: budget-stop followup, missing-context guard, explicit new chat');
})().catch(error=>{console.error(error);process.exitCode=1;});
