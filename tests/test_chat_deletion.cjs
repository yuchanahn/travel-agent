const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/travel_agent/static/app.js','utf8');
let accepted=false,requests=0,clears=0,refreshes=0,errorMessage='',failure=false;
let deleted=['other'],stored='current';
const context=vm.createContext({activeId:'current',window:{confirm:()=>accepted},
  $:()=>({click(){clears++;context.activeId=null;stored=null;}}),
  localStorage:{getItem:()=>stored,removeItem(){stored=null;}},
  async api(path,options){requests++;assert.equal(options.method,'DELETE');
    if(failure)throw new Error('Still running');return {deleted_ids:deleted};},
  async history(){refreshes++;},error(message){errorMessage=message;}});
vm.runInContext(source.slice(source.indexOf('async function deleteConversation('),source.indexOf('async function history()')),context);
(async()=>{
  await context.deleteConversation({conversation_id:'root'});
  assert.equal(requests,0,'Cancel leaves conversation untouched');
  accepted=true;
  await context.deleteConversation({conversation_id:'root'});
  assert.equal(clears,0,'Deleting another chat preserves active chat');
  deleted=['current'];failure=true;
  await context.deleteConversation({conversation_id:'root'});
  assert.equal(clears,0,'Failed deletion preserves active chat');
  assert.equal(errorMessage,'Still running');
  failure=false;
  await context.deleteConversation({conversation_id:'root'});
  assert.equal(clears,1);assert.equal(stored,null);assert.equal(refreshes,2);
  console.log('PASS: deletion cancel, active-chat preservation, failure handling, successful reset');
})().catch(error=>{console.error(error);process.exitCode=1;});
