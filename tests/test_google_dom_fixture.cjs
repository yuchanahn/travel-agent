'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {applyConstructorText}=require('../scripts/probe_google_dom.cjs');

test('constructor text fixture preserves constructor identity and other function behavior',()=>{
  const context=vm.createContext({});
  vm.runInContext('class Navigator{};class HTMLMediaElement{};function example(){return 7};globalThis.saved=Navigator;globalThis.other=String(example)',context);
  applyConstructorText({eval:source=>vm.runInContext(source,context)});
  assert.equal(vm.runInContext('Navigator===saved && new Navigator() instanceof saved',context),true);
  assert.equal(vm.runInContext('String(example)===other && example()===7',context),true);
  assert.equal(vm.runInContext('String(Navigator)',context),'function Navigator() { [native code] }');
  assert.equal(vm.runInContext('try{Function.prototype.toString.call({})}catch(e){e.name}',context),'TypeError');
});
