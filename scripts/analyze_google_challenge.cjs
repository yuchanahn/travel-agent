// Offline adapter for Sec-CH-Lemon's reviewed toolkit. No HTTP calls or browser.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const [toolkit, capture, output] = process.argv.slice(2);
const {run,longestRecord} = require(path.join(toolkit,'part-2-reverse-vm/tools/record-recover.cjs'));
const {extract} = require(path.join(toolkit,'part-1-proxy-probe/lib/challenge.js'));
const {probe} = require(path.join(toolkit,'part-1-proxy-probe/probe-proxy.js'));
(async()=>{
  const html=fs.readFileSync(capture,'utf8');
  const control=await run(html,false);const tapped=await run(html,true);
  if(control.err||tapped.err)throw Error('record_analysis_failed');
  const record=longestRecord(tapped.streams);
  const access=await probe(extract(capture));
  fs.writeFileSync(output,JSON.stringify({token:tapped.token,record:record.plain,access},null,2));
  console.log(JSON.stringify({
    vm_build:crypto.createHash('sha256').update(tapped.challenge.vm).digest('hex').slice(0,12),
    vm_characters:tapped.challenge.vm.length,token_length:tapped.token.length,
    record_instrumentation_equal:control.token===tapped.token,
    record_bytes:record.plain.length,access_instrumentation_equal:access.invisible,
    access_rows:access.rows.length,surfaces:[...access.surfaces],
    property_paths:[...new Set(access.rows.map(r=>r.key))],
    server_acceptance_tested:false
  },null,2));
})().catch(()=>{console.log(JSON.stringify({status:'analysis_failed',server_acceptance_tested:false}));process.exitCode=1});
