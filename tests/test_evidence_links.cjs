const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('src/travel_agent/static/app.js','utf8');
function element(tag){return {tag,children:[],append(...items){this.children.push(...items);}};}
const context=vm.createContext({URL,document:{createElement:element,createTextNode:text=>({text})},
  sources:new Map([['web:0123456789abcdef',{url:'https://example.org/evidence'}]])});
vm.runInContext(source.slice(source.indexOf('function node('),source.indexOf('function markdown(')),context);
const parent=element('p');
context.inline(parent,'예약: <https://www.airbnb.com/rooms/123> https://www.yeogi.com/domestic-accommodations/456 [\u200bweb:0123456789abcdef]');
const links=parent.children.filter(n=>n.tag==='a');
assert.deepEqual(links.map(n=>n.href),['https://www.airbnb.com/rooms/123','https://www.yeogi.com/domestic-accommodations/456','https://example.org/evidence']);
const unsafe=element('p');context.inline(unsafe,'[실행](javascript:alert(1))');
assert.equal(unsafe.children.filter(n=>n.tag==='a').length,0);
console.log('PASS: bare/angle booking links, zero-width citation, unsafe protocol remains text');
