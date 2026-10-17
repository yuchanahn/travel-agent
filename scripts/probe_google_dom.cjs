'use strict';
// Research harness only. No browser, page resource loading, or network access.
const fs = require('node:fs');
const path = require('node:path');

function applyEnvironment(w, mode, envSource) {
  if (!['baseline', 'screen', 'profile'].includes(mode)) throw Error('unknown_mode');
  if (mode === 'baseline') return;
  const screen = {width:1920,height:1080,availWidth:1920,availHeight:1040,
    availLeft:0,availTop:0,colorDepth:24,pixelDepth:24};
  if (mode === 'screen') {
    for (const [key,value] of Object.entries(screen)) {
      Object.defineProperty(w.screen,key,{configurable:true,get:()=>value});
    }
    return;
  }
  // Explicit synthetic fixture, not a fingerprint collected from the user's browser.
  w.eval(envSource({screen,platform:'MacIntel',vendor:'Google Inc.',productSub:'20030107',
    languages:['en-US','en'],hardwareConcurrency:8,deviceMemory:8,maxTouchPoints:0,
    pdfViewerEnabled:true,devicePixelRatio:1,innerWidth:1920,innerHeight:969,
    outerWidth:1920,outerHeight:1080,isSecureContext:true,
    chromeKeys:['app','csi','loadTimes']}));
}

async function main() {
  const [toolkit,inputFile,outputFile,mode] = process.argv.slice(2);
  const modules = path.join(toolkit,'part-2-reverse-vm/node_modules');
  const {JSDOM,VirtualConsole} = require(path.join(modules,'jsdom'));
  const {implSymbol} = require(path.join(modules,'jsdom/lib/generated/idl/utils.js'));
  const {serializeURL} = require(path.join(modules,'whatwg-url'));
  const {envSource} = require(path.join(toolkit,'part-2-reverse-vm/tools/lib/challenge.js'));
  const input = JSON.parse(fs.readFileSync(inputFile,'utf8'));
  const errors=[],beacons=[],redirects=[];
  const vc = new VirtualConsole();
  vc.on('jsdomError',e=>errors.push(e.name));
  const dom = new JSDOM(input.html,{url:input.url,referrer:'https://www.google.com/',
    runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
  const w = dom.window;
  try {
    w.navigator.sendBeacon = url=>{beacons.push(String(url));return true;};
    Object.defineProperty(w.navigator,'userAgent',{value:input.ua,configurable:true});
    Object.defineProperty(w.navigator,'platform',{value:'MacIntel',configurable:true});
    applyEnvironment(w,mode,envSource);
    for (const [key,value] of Object.entries(input.cookies)) {
      w.document.cookie = key+'='+value+'; path=/; secure';
    }
    let done;
    const finished = new Promise(resolve=>{done=resolve;});
    w.location[implSymbol]._locationObjectNavigate = url=>{redirects.push(serializeURL(url));done();};
    for (const script of w.document.querySelectorAll('script:not([src])')) {
      try { w.eval(script.textContent); } catch(e) { errors.push(e.name); }
    }
    const timer = setTimeout(done,5000);
    await finished;
    clearTimeout(timer);
    const cookies = Object.fromEntries(w.document.cookie.split(';').filter(x=>x.includes('='))
      .map(x=>{const i=x.indexOf('=');return [x.slice(0,i).trim(),x.slice(i+1)];}));
    fs.writeFileSync(outputFile,JSON.stringify({cookies,redirects,errors,beacons}));
    console.log(JSON.stringify({mode,cookie_names:Object.keys(cookies),
      sg_ss_length:(cookies.SG_SS||'').length,redirect_count:redirects.length,errors}));
  } finally { w.close(); }
}

module.exports = {applyEnvironment};
if (require.main === module) main().catch(e=>{
  console.log(JSON.stringify({status:'dom_probe_failed',error_type:e.name}));process.exitCode=1;
});
