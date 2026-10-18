'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {applyConstructorText,mirrorIframeNavigator,observeDomAccess}=require('../scripts/probe_google_dom.cjs');

test('constructor text fixture preserves constructor identity and other function behavior',()=>{
  const context=vm.createContext({});
  vm.runInContext('class Navigator{};class HTMLMediaElement{};function example(){return 7};globalThis.saved=Navigator;globalThis.other=String(example)',context);
  applyConstructorText({eval:source=>vm.runInContext(source,context)});
  assert.equal(vm.runInContext('Navigator===saved && new Navigator() instanceof saved',context),true);
  assert.equal(vm.runInContext('String(example)===other && example()===7',context),true);
  assert.equal(vm.runInContext('String(Navigator)',context),'function Navigator() { [native code] }');
  assert.equal(vm.runInContext('try{Function.prototype.toString.call({})}catch(e){e.name}',context),'TypeError');
});

function iframeFixture() {
  const innerContext=vm.createContext({});
  vm.runInContext('navigator={userAgent:"jsdom",platform:"",languages:["en-US"]}',innerContext);
  const inner=vm.runInContext('globalThis',innerContext);
  const context=vm.createContext({otherWindow:inner});
  vm.runInContext(`navigator={userAgent:"Chrome",platform:"MacIntel",languages:["en-US","en"]};
    class Frame{get contentWindow(){if(!(this instanceof Frame))throw new TypeError('receiver');return otherWindow}}
    globalThis.HTMLIFrameElement=Frame;globalThis.frame=new Frame()`,context);
  return {parent:vm.runInContext('globalThis',context),inner};
}

test('iframe proxy control preserves getter shape, receiver checks and frame own keys',()=>{
  const {parent,inner}=iframeFixture();
  const original=Object.getOwnPropertyDescriptor(parent.HTMLIFrameElement.prototype,'contentWindow').get;
  const stats=mirrorIframeNavigator(parent,false);
  const getter=Object.getOwnPropertyDescriptor(parent.HTMLIFrameElement.prototype,'contentWindow').get;
  assert.equal(Object.getPrototypeOf(getter),Object.getPrototypeOf(original));
  assert.equal(getter.name,original.name);assert.equal(getter.length,original.length);
  assert.equal(Object.hasOwn(parent.frame,'contentWindow'),false);
  assert.equal(parent.frame.contentWindow,inner);
  assert.equal(inner.navigator.userAgent,'jsdom');assert.equal(stats.mirrored,0);
  assert.throws(()=>getter.call({}),e=>e.name==='TypeError');
});

test('iframe mirror uses child-realm arrays and applies each window once',()=>{
  const {parent,inner}=iframeFixture();
  const stats=mirrorIframeNavigator(parent,true);
  assert.equal(parent.frame.contentWindow,inner);
  assert.equal(parent.frame.contentWindow,inner);
  assert.equal(inner.navigator.userAgent,'Chrome');
  assert.equal(inner.navigator.languages.constructor,inner.Array);
  assert.equal(stats.mirrored,1);assert.equal(stats.window_reads,2);
  assert.ok(stats.mismatched_fields.includes('userAgent'));
});

test('DOM observation preserves calls/errors and never records argument or result text',()=>{
  const context=vm.createContext({});
  vm.runInContext(`class Node{get nodeValue(){return 'PRIVATE RESULT'}
    appendChild(value){if(!(this instanceof Node))throw new TypeError('receiver');return value}}
    globalThis.Node=Node;globalThis.node=new Node()`,context);
  const w=vm.runInContext('globalThis',context);
  const stats=observeDomAccess(w);
  const value={text:'PRIVATE ARGUMENT'};
  assert.equal(w.node.nodeValue,'PRIVATE RESULT');
  assert.equal(w.node.appendChild(value),value);
  assert.throws(()=>w.Node.prototype.appendChild.call({},value),e=>e.name==='TypeError');
  assert.equal(stats.rows.find(row=>row.path==='Node.appendChild').throws,1);
  assert.equal(JSON.stringify(stats).includes('PRIVATE'),false);
});
