// Offline, one-input-at-a-time record experiment. The Google VM is unmodified.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

function applyFixture(window, fixture, dom) {
  const set = (object, key, value) => Object.defineProperty(object, key, {value, configurable:true});
  if (fixture.url) dom.reconfigure({url:fixture.url});
  if (fixture.languages) set(window.navigator,'languages',fixture.languages);
  if (fixture.screenWidth !== undefined) set(window.screen,'width',fixture.screenWidth);
  if (fixture.hardwareConcurrency !== undefined) set(window.navigator,'hardwareConcurrency',fixture.hardwareConcurrency);
  if (fixture.userAgent) set(window.navigator,'userAgent',fixture.userAgent);
  if (fixture.webdriver !== undefined) set(window.navigator,'webdriver',fixture.webdriver);
  if (fixture.navigatorStub) window.Navigator=function Navigator(){};
}

function compareRecords(left, right) {
  let prefix=0;
  while(prefix<Math.min(left.length,right.length)&&left[prefix]===right[prefix])prefix++;
  let suffix=0;
  while(suffix<Math.min(left.length,right.length)-prefix && left[left.length-1-suffix]===right[right.length-1-suffix])suffix++;
  const positions=[];
  for(let i=0;i<Math.max(left.length,right.length);i++)if(left[i]!==right[i])positions.push(i);
  const ranges=[];
  for(const p of positions){const last=ranges[ranges.length-1];if(last&&last[1]===p)last[1]=p+1;else ranges.push([p,p+1]);}
  return {equal:positions.length===0,left_bytes:left.length,right_bytes:right.length,
          common_prefix_bytes:prefix,common_suffix_bytes:suffix,
          positional_difference_count:positions.length,difference_ranges:ranges};
}

function makeRunner(toolkit) {
  const filename=path.join(toolkit,'part-2-reverse-vm/tools/record-recover.cjs');
  let source=fs.readFileSync(filename,'utf8');
  const declaration='function run(html, tapped) {';
  const anchor='w.navigator.sendBeacon = () => true;';
  const timeout='timer = setTimeout(() => finish({ err: \'timed out\' }), 30000);';
  if(source.split(declaration).length!==2||source.split(anchor).length!==2||source.split(timeout).length!==2)throw Error('unsupported_toolkit_harness');
  source=source.replace(declaration,'function run(html, tapped, fixture = {}) {')
               .replace(anchor,anchor+'\n    applyFixture(w, fixture, dom);')
               .replace(timeout,timeout.replace('30000','3000'));
  // Edit only the host harness in memory, before VM execution. Never edit the
  // captured interpreter or encrypted program. Preserve upstream files on disk.
  source='const {applyFixture}=require('+JSON.stringify(__filename)+');\n'+source;
  const loaded=new Module(filename,module);
  loaded.filename=filename;loaded.paths=Module._nodeModulePaths(path.dirname(filename));
  loaded._compile(source,filename);
  return loaded.exports;
}

async function main() {
  const [toolkit,capture,output,...requested]=process.argv.slice(2);
  const {run,longestRecord}=makeRunner(toolkit);
  const html=fs.readFileSync(capture,'utf8');
  const allVariants=[
    ['baseline',{}],['baseline_repeat',{}],
    ['language_first',{languages:['ko-KR','en']}],
    ['language_second',{languages:['en-US','ko']}],
    ['screen_width',{screenWidth:1}],
    ['screen_width_256',{screenWidth:256}],
    ['screen_width_257',{screenWidth:257}],
    ['hardware_concurrency',{hardwareConcurrency:1}],
    ['query_only',{url:'https://www.google.com/search?q=synthetic'}],
    ['user_agent_only',{userAgent:'Synthetic-HTTP-Test/1.0'}],
    ['webdriver_negative_control',{webdriver:true}],
    ['navigator_constructor_stub',{navigatorStub:true}],
  ];
  const selected=requested.length?requested:['language_first','language_second','screen_width'];
  if(selected.some(name=>!allVariants.some(([key])=>key===name)))throw Error('unknown_case');
  const variants=allVariants.filter(([name])=>name.startsWith('baseline')||selected.includes(name));
  const records=[],summary=[];
  const started=Date.now();
  const checkpoint=()=>{
    const result={variants:summary,baseline_reproducible:summary[1]?.equal===true,
                  server_acceptance_tested:false,elapsed_ms:Date.now()-started};
    fs.writeFileSync(output+'.tmp',JSON.stringify({summary:result,records},null,2));
    fs.renameSync(output+'.tmp',output);return result;
  };
  for(const [name,fixture] of variants){
    const caseStarted=Date.now();
    const control=await run(html,false,fixture),tapped=await run(html,true,fixture);
    if(control.err||tapped.err){
      summary.push({name,fixture,status:'execution_failed',control_error:control.err||null,tapped_error:tapped.err||null,
                    elapsed_ms:Date.now()-caseStarted});checkpoint();
      if(name.startsWith('baseline'))throw Error('baseline_failed');
      continue;
    }
    const plain=longestRecord(tapped.streams).plain;
    const equal=control.token===tapped.token;
    const first=records[0]?.record||plain;
    records.push({name,fixture,token:tapped.token,record:plain});
    summary.push({name,fixture,instrumentation_equal:equal,elapsed_ms:Date.now()-caseStarted,token_length:tapped.token.length,
                  record_bytes:plain.length,...compareRecords(first,plain)});
    checkpoint();
    if(!equal)throw Error('instrumentation_changed_output');
    process.stderr.write(name+' completed\n');
  }
  const result=checkpoint();
  console.log(JSON.stringify(result,null,2));
}
module.exports={applyFixture,compareRecords,makeRunner};
if(require.main===module)main().catch(()=>{console.log(JSON.stringify({status:'matrix_failed',server_acceptance_tested:false}));process.exitCode=1});
