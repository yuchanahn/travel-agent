'use strict';
// Research harness only. No browser, page resource loading, or network access.
const fs = require('node:fs');
const path = require('node:path');

function applyEnvironment(w, mode, envSource, identity = {}) {
  if (!['baseline', 'screen', 'profile', 'constructor-text', 'iframe-mirror'].includes(mode)) throw Error('unknown_mode');
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
  w.eval(envSource({screen,platform:identity.platform||'MacIntel',vendor:identity.vendor??'Google Inc.',productSub:'20030107',
    languages:['en-US','en'],hardwareConcurrency:8,deviceMemory:8,maxTouchPoints:0,
    pdfViewerEnabled:true,devicePixelRatio:1,innerWidth:1920,innerHeight:969,
    outerWidth:1920,outerHeight:1080,isSecureContext:true,
    chromeKeys:identity.chrome===false?[]:['app','csi','loadTimes']}));
  if (mode === 'constructor-text') applyConstructorText(w);
  if (mode === 'iframe-mirror') return mirrorIframeNavigator(w,true);
}

function mirrorIframeNavigator(w, mirror) {
  // Preserve the original getter's prototype/name/length and frame own keys.
  const prototype = w.HTMLIFrameElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype,'contentWindow');
  if (!descriptor?.get) throw Error('iframe_window_getter_missing');
  const seen = new WeakSet();
  const keys = ['userAgent','platform','vendor','language','languages','hardwareConcurrency',
    'deviceMemory','maxTouchPoints','pdfViewerEnabled','cookieEnabled'];
  const stats = {window_reads:0,windows_seen:0,mirrored:0,mismatched_fields:[]};
  const getter = new w.Proxy(descriptor.get,{apply(target,self,args){
    stats.window_reads++;
    const inner = Reflect.apply(target,self,args);
    if (inner && !seen.has(inner)) {
      seen.add(inner);stats.windows_seen++;
      const values = {};
      for (const key of keys) {
        const parentValue = w.navigator[key];
        if (JSON.stringify(parentValue)!==JSON.stringify(inner.navigator[key]) && !stats.mismatched_fields.includes(key)) stats.mismatched_fields.push(key);
        if (parentValue !== undefined) values[key] = parentValue;
      }
      if (mirror) {
        inner.eval('(function(values){for(const [key,value] of Object.entries(values))Object.defineProperty(navigator,key,{configurable:true,get:()=>value});})('+JSON.stringify(values)+')');
        stats.mirrored++;
      }
    }
    return inner;
  }});
  Object.defineProperty(prototype,'contentWindow',{...descriptor,get:getter});
  return stats;
}

function observeDomAccess(w, captureSetters = false) {
  const rows = [], index = new Map(), private_setter_values=[];
  const wrap = (fn,path,operation)=>new w.Proxy(fn,{apply(target,self,args){
    if(captureSetters && operation==='set' && ['HTMLIFrameElement.srcdoc','Element.innerHTML'].includes(path)
       && typeof args[0]==='string' && args[0].length<=4096){private_setter_values.push({path,text:args[0]});}
    let result,failed=false;
    try {result=Reflect.apply(target,self,args);return result;}
    catch(error){failed=true;throw error;}
    finally {
      const key=operation+':'+path;
      let row=index.get(key);
      if(!row){row={path,operation,count:0,throws:0,result_types:[]};index.set(key,row);rows.push(row);}
      row.count++;if(failed)row.throws++;
      const type=result===null?'null':typeof result;
      if(!row.result_types.includes(type))row.result_types.push(type);
    }
  }});
  const classes=['HTMLIFrameElement','HTMLAnchorElement','HTMLElement','Element','Node','CSSStyleDeclaration'];
  let wrapped=0;
  for(const name of classes){
    const prototype=w[name]?.prototype;
    if(!prototype)continue;
    for(const key of Object.getOwnPropertyNames(prototype)){
      if(key==='constructor')continue;
      const descriptor=Object.getOwnPropertyDescriptor(prototype,key);
      if(!descriptor.configurable)continue;
      const next={...descriptor};
      for(const part of ['get','set','value']){
        if(typeof descriptor[part]==='function'){
          next[part]=wrap(descriptor[part],name+'.'+key,part==='value'?'call':part);wrapped++;
        }
      }
      Object.defineProperty(prototype,key,next);
    }
  }
  // Normal counters omit argument/result text. Opt-in setter content is private
  // and must be removed by publicFixture before printing a summary.
  return captureSetters?{wrapped,rows,private_setter_values}:{wrapped,rows};
}

function applyConstructorText(w) {
  // Narrow research fixture: change serialization of TWO parent constructors.
  // Preserve their identity/prototypes/call behavior. Does not emulate a browser.
  w.eval(`(function(){
    const original = Function.prototype.toString;
    const sources = new Map([[Navigator,'function Navigator() { [native code] }'],
      [HTMLMediaElement,'function HTMLMediaElement() { [native code] }']]);
    Object.defineProperty(Function.prototype,'toString',{configurable:true,writable:true,
      value:function toString(){return sources.has(this)?sources.get(this):original.call(this);}});
  })()`);
}

function wrapIframeSource(w, changeText) {
  const original = w.document.createElement;
  const seen = new WeakSet();
  const stats = {created:0,window_reads:0,patched:0};
  w.document.createElement = function(...args) {
    const element = Reflect.apply(original,this,args);
    if (element.tagName !== 'IFRAME') return element;
    stats.created++;
    let prototype = Object.getPrototypeOf(element), descriptor;
    while (prototype && !descriptor) {
      descriptor = Object.getOwnPropertyDescriptor(prototype,'contentWindow');
      prototype = Object.getPrototypeOf(prototype);
    }
    if (!descriptor?.get) throw Error('iframe_window_getter_missing');
    Object.defineProperty(element,'contentWindow',{configurable:true,get(){
      stats.window_reads++;
      const inner = descriptor.get.call(this);
      if (changeText && inner && !seen.has(inner)) {
        applyConstructorText(inner);
        seen.add(inner);
        stats.patched++;
      }
      return inner;
    }});
    return element;
  };
  return stats;
}

function auditRuntime(w) {
  // Run only AFTER the challenge completed and its cookies were read.
  const native = fn=>/\{\s*\[native code\]\s*\}/.test(w.Function.prototype.toString.call(fn));
  const frame = w.document.createElement('iframe');
  const detached = frame.contentWindow;
  w.document.body.appendChild(frame);
  const inner = frame.contentWindow;
  const result = {navigator_source_looks_native:native(w.Navigator),
    media_source_looks_native:native(w.HTMLMediaElement),
    detached_iframe_window:detached===null?'null':typeof detached,
    attached_iframe_window:typeof inner,
    distinct_iframe_function:!!inner && inner.Function!==w.Function,
    iframe_navigator_source_looks_native:inner?native(inner.Navigator):null};
  frame.remove();
  return result;
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
    Object.defineProperty(w.navigator,'platform',{value:input.identity?.platform||'MacIntel',configurable:true});
    if (input.identity) Object.defineProperty(w.navigator,'vendor',{value:input.identity.vendor,configurable:true});
    const fixtureStats = applyEnvironment(w,mode,envSource,input.identity);
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
    // Audit creates its own frame; snapshot the challenge's counters first.
    const challengeFixtureStats = fixtureStats?JSON.parse(JSON.stringify(fixtureStats)):null;
    const runtime = auditRuntime(w);
    fs.writeFileSync(outputFile,JSON.stringify({cookies,redirects,errors,beacons}));
    console.log(JSON.stringify({mode,cookie_names:Object.keys(cookies),
      sg_ss_length:(cookies.SG_SS||'').length,redirect_count:redirects.length,errors,runtime,fixture:challengeFixtureStats}));
  } finally { w.close(); }
}

module.exports = {applyEnvironment,applyConstructorText,wrapIframeSource,mirrorIframeNavigator,observeDomAccess,auditRuntime};
if (require.main === module) main().catch(e=>{
  console.log(JSON.stringify({status:'dom_probe_failed',error_type:e.name}));process.exitCode=1;
});
