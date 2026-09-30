// Runs the production client against a tiny DOM/fetch adapter. This checks state
// and asynchronous races; it does not claim browser layout or accessibility coverage.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root,'src/ladderproof/assets/app.js'),'utf8');
const certificate = JSON.parse(fs.readFileSync(path.join(root,'examples/six-bit-one-percent.certificate.json'),'utf8'));
const copy = value => JSON.parse(JSON.stringify(value));
const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.listeners={};this.attributes={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.classes=new Set();this.classList={toggle:(c,on)=>on===undefined?(this.classes.has(c)?this.classes.delete(c):this.classes.add(c)):(on?this.classes.add(c):this.classes.delete(c))};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(type,callback){this.listeners[type]=callback;}
  emit(type){return this.listeners[type]?.({target:this});}
  click(){return this.emit('click');}
  remove(){}
}
function setup(initialDesign=null){
  const nodes={};for(const match of fs.readFileSync(path.join(root,'src/ladderproof/assets/index.html'),'utf8').matchAll(/id="([^"]+)"/g))nodes[match[1]]=new Element();
  nodes.bits.value='6';nodes.vref.value='1';nodes.title.value='6-bit R-2R ladder';
  const presets=['1/100','1/20','0'].map(t=>{const e=new Element('button');e.dataset.tolerance=t;return e;});
  const walk=node=>[node,...node.children.filter(x=>x instanceof Element).flatMap(walk)];
  const requests=[];let handler=()=>{throw Error('Unexpected endpoint');};
  const context=vm.createContext({console,setTimeout,clearTimeout,Blob,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}},document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag),createElementNS:(_ns,tag)=>new Element(tag),createTextNode:text=>({textContent:text}),body:new Element('body'),querySelectorAll:selector=>selector==='[data-tolerance]'?presets:walk(nodes['resistor-rows']).filter(e=>e.dataset.part!==undefined)},fetch:async(url,options)=>{const request={url,body:options.body?JSON.parse(options.body):null,raw:options.body};requests.push(request);const firstDefault=url==='/api/design'&&requests.filter(r=>r.url==='/api/design').length===1;const payload=firstDefault?(initialDesign?await initialDesign:copy(certificate.design)):await handler(request);return {ok:!payload._error,status:payload._error?400:200,json:async()=>payload._error?{error:payload._error}:payload};}});
  vm.runInContext(source,context,{filename:'app.js'});
  return {nodes,presets,requests,evaluate:s=>vm.runInContext(s,context),handle:f=>handler=f,inputs:()=>walk(nodes['resistor-rows']).filter(e=>e.dataset.part!==undefined)};
}
test('renders actual complete certificate, code bounds, binary witness and step bounds',async()=>{
  const app=setup();await sleep(0);app.handle(r=>r.url==='/api/jobs'?{id:'a',state:'running'}:{state:'complete',result:copy(certificate)});app.nodes.analyze.click();await sleep(230);
  assert.equal(app.evaluate('state.certificate.results.worst_transition.step'),certificate.results.worst_transition.step);
  assert.equal(app.nodes['bound-rows'].children.length,64);assert.equal(app.inputs().length,36);
  assert.match(app.nodes['binary-transition'].textContent,/011111 → 100000/);
  assert.match(app.nodes['resources'].textContent,/4096 corners/);
  app.nodes['steps-tab'].click();assert.equal(app.nodes['bound-rows'].children.length,63);
  assert.equal(app.nodes['exact-min'].textContent,certificate.results.worst_transition.step+' V');
  assert.equal(app.nodes['result-state'].textContent,'Complete enumeration');
  const input=app.inputs()[1];input.value='1970';input.emit('input');
  assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);assert.equal(app.nodes['result-content'].hidden,true);
});
test('late start response is cancelled and cannot replace an edited design',async()=>{
  const app=setup();await sleep(0);let release;app.handle(r=>r.url==='/api/jobs'?new Promise(resolve=>release=resolve):{state:'cancelled'});app.nodes.analyze.click();app.nodes.vref.value='2';app.nodes.vref.emit('input');release({id:'late',state:'running'});await sleep(10);
  assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.evaluate('state.design.vref'),'2');assert.ok(app.requests.some(r=>r.url==='/api/jobs/late/cancel'));
});
test('late completed poll result cannot replace input changed during computation',async()=>{
  const app=setup();await sleep(0);let release;app.handle(r=>r.url==='/api/jobs'?{id:'old',state:'running'}:r.url.endsWith('/cancel')?{state:'cancelled'}:new Promise(resolve=>release=resolve));app.nodes.analyze.click();await sleep(215);assert.ok(release);app.nodes.title.value='New immutable design';app.nodes.title.emit('input');release({state:'complete',result:copy(certificate)});await sleep(10);
  assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.evaluate('state.design.title'),'New immutable design');assert.equal(app.nodes['result-state'].textContent,'No certificate');
});
test('refused computation exposes its error and never enables certificate export',async()=>{
  const app=setup();await sleep(0);app.handle(r=>r.url==='/api/jobs'?{id:'timeout',state:'running'}:{state:'refused',error:'Deadline exceeded. No certificate.'});app.nodes.analyze.click();await sleep(230);
  assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);assert.match(app.nodes.status.textContent,/Deadline exceeded/);assert.equal(app.nodes.cancel.hidden,true);
});
test('imported certificate remains unverified until complete verifier result, then displays verified',async()=>{
  const app=setup();await sleep(0);let release;app.handle(r=>r.url==='/api/import-certificate'?r.body:r.url==='/api/jobs'?{id:'import',state:'running'}:new Promise(resolve=>release=resolve));app.nodes['certificate-file'].files=[{size:1000,text:async()=>JSON.stringify(certificate)}];await app.nodes['certificate-file'].emit('change');await sleep(215);
  assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['result-state'].textContent,'No certificate');
  release({state:'complete',result:{status:'verified',corner_count:4096}});await sleep(10);
  assert.equal(app.nodes['result-state'].textContent,'Independently verified');assert.equal(app.evaluate('state.certificate.corner_count'),4096);
});
test('failed imported certificate remains hidden and exact individual preset arithmetic preserves nominal',async()=>{
  const app=setup();await sleep(0);app.handle(r=>r.url==='/api/import-certificate'?r.body:r.url==='/api/jobs'?{id:'bad',state:'running'}:{state:'failed',error:'Independent recomputation mismatch'});app.nodes['certificate-file'].files=[{size:1000,text:async()=>JSON.stringify(certificate)}];await app.nodes['certificate-file'].emit('change');await sleep(230);
  assert.equal(app.evaluate('state.certificate'),null);assert.match(app.nodes.status.textContent,/mismatch/);
  const input=app.inputs()[0];input.value='1/3';input.emit('input');app.presets[0].click();assert.equal(app.evaluate('state.design.resistors[0].nominal'),'1/3');assert.equal(app.evaluate('state.design.resistors[0].min'),'33/100');assert.equal(app.evaluate('state.design.resistors[0].max'),'101/300');
  assert.equal(app.evaluate("display('100000')"),'100000');
});
test('delayed design file read gates old analysis and accepts a new generation',async()=>{
  const app=setup();await sleep(0);let releaseRead;const incoming=copy(certificate.design);incoming.title='Imported exact design';incoming.resistors[0].min='1970';
  app.handle(r=>r.url==='/api/import-design'?r.body:r.url==='/api/validate'?r.body.design:{id:'conflict',state:'running'});
  app.nodes['design-file'].files=[{size:1000,text:()=>new Promise(resolve=>releaseRead=resolve)}];const importing=app.nodes['design-file'].emit('change');const revision=app.evaluate('state.revision');
  assert.equal(app.nodes.analyze.disabled,true);app.nodes.analyze.click();assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);
  releaseRead(JSON.stringify(incoming));await importing;assert.ok(app.evaluate('state.revision')>revision);assert.equal(app.evaluate('state.design.title'),'Imported exact design');assert.equal(app.evaluate('state.design.resistors[0].min'),'1970');assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);
});
test('delayed design validation gates analysis and a later input edit supersedes the import',async()=>{
  const app=setup();await sleep(0);let release;app.handle(r=>r.url==='/api/import-design'||r.url==='/api/validate'?new Promise(resolve=>release=resolve):{id:'conflict',state:'running'});
  const incoming=copy(certificate.design);incoming.title='Discard this delayed import';app.nodes['design-file'].files=[{size:1000,text:async()=>JSON.stringify(incoming)}];const importing=app.nodes['design-file'].emit('change');await sleep(0);
  assert.equal(app.nodes.analyze.disabled,true);app.nodes.analyze.click();assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);
  app.nodes.title.value='Later user edit survives';app.nodes.title.emit('input');release(incoming);await importing;
  assert.equal(app.evaluate('state.design.title'),'Later user edit survives');assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);
});
test('new imported design survives an old poll result after import acceptance',async()=>{
  const app=setup();await sleep(0);let releasePoll;app.handle(r=>r.url==='/api/jobs'?{id:'before-import',state:'running'}:r.url.endsWith('/cancel')?{state:'cancelled'}:r.url==='/api/import-design'?r.body:r.url==='/api/validate'?r.body.design:new Promise(resolve=>releasePoll=resolve));app.nodes.analyze.click();await sleep(215);
  const incoming=copy(certificate.design);incoming.title='Replacement must survive';incoming.vref='2';app.nodes['design-file'].files=[{size:1000,text:async()=>JSON.stringify(incoming)}];await app.nodes['design-file'].emit('change');releasePoll({state:'complete',result:copy(certificate)});await sleep(10);
  assert.equal(app.evaluate('state.design.title'),'Replacement must survive');assert.equal(app.evaluate('state.design.vref'),'2');assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);assert.ok(app.requests.some(r=>r.url==='/api/jobs/before-import/cancel'));
});
test('delayed defaults gate old analysis and preserve a later reference edit',async()=>{
  const app=setup();await sleep(0);let release;app.handle(r=>r.url==='/api/design'?new Promise(resolve=>release=resolve):{id:'conflict',state:'running'});app.nodes.bits.value='5';const loading=app.nodes.bits.emit('change');
  assert.equal(app.nodes.analyze.disabled,true);app.nodes.analyze.click();assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);
  app.nodes.vref.value='3/2';app.nodes.vref.emit('input');const incoming=copy(certificate.design);incoming.title='Stale default';release(incoming);await sleep(10);
  assert.equal(app.evaluate('state.design.vref'),'3/2');assert.equal(app.nodes.bits.value,'6');assert.equal(app.evaluate('state.design.title'),certificate.design.title);assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);
});
test('accepted defaults replace generation and stale earlier analysis stays hidden',async()=>{
  const app=setup();await sleep(0);let releasePoll,releaseDefault;app.handle(r=>r.url==='/api/jobs'?{id:'before-default',state:'running'}:r.url.endsWith('/cancel')?{state:'cancelled'}:r.url==='/api/design'?new Promise(resolve=>releaseDefault=resolve):new Promise(resolve=>releasePoll=resolve));app.nodes.analyze.click();await sleep(215);app.nodes.bits.value='6';app.nodes.bits.emit('change');const revision=app.evaluate('state.revision');const incoming=copy(certificate.design);incoming.title='Accepted fresh defaults';releaseDefault(incoming);await sleep(0);releasePoll({state:'complete',result:copy(certificate)});await sleep(10);
  assert.ok(app.evaluate('state.revision')>revision);assert.equal(app.evaluate('state.design.title'),'Accepted fresh defaults');assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);
});
test('design and certificate file imports preserve duplicate fields for strict server rejection',async()=>{
  const app=setup();await sleep(0);app.evaluate(`showCertificate(${JSON.stringify(certificate)})`);assert.equal(app.nodes['export-certificate'].disabled,false);app.handle(r=>({ _error:'Duplicate JSON field: vref' }));const rawDesign=JSON.stringify(certificate.design).replace('"vref":"1"','"vref":"2","vref":"1"');
  app.nodes['design-file'].files=[{size:rawDesign.length,text:async()=>rawDesign}];await app.nodes['design-file'].emit('change');assert.equal(app.requests.at(-1).raw,rawDesign);assert.equal(app.requests.at(-1).url,'/api/import-design');assert.match(app.nodes.status.textContent,/Duplicate/);assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);
  const rawCert=JSON.stringify(certificate).replace('"vref":"1"','"vref":"2","vref":"1"');app.nodes['certificate-file'].files=[{size:rawCert.length,text:async()=>rawCert}];await app.nodes['certificate-file'].emit('change');assert.equal(app.requests.at(-1).raw,rawCert);assert.equal(app.requests.at(-1).url,'/api/import-certificate');assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);
});
test('delayed certificate read blocks analysis and is discarded after a later edit',async()=>{
  const app=setup();await sleep(0);let releaseRead;app.handle(r=>r.body);app.nodes['certificate-file'].files=[{size:1000,text:()=>new Promise(resolve=>releaseRead=resolve)}];const importing=app.nodes['certificate-file'].emit('change');
  assert.equal(app.nodes.analyze.disabled,true);app.nodes.analyze.click();assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);app.nodes.vref.value='7/4';app.nodes.vref.emit('input');releaseRead(JSON.stringify(certificate));await importing;
  assert.equal(app.evaluate('state.design.vref'),'7/4');assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);assert.equal(app.requests.filter(r=>r.url==='/api/import-certificate').length,0);
});
test('late certificate parse failure does not replace a newer edit or its status',async()=>{
  const app=setup();await sleep(0);let release;app.handle(r=>r.url==='/api/import-certificate'?new Promise(resolve=>release=resolve):r.body);app.nodes['certificate-file'].files=[{size:1000,text:async()=>JSON.stringify(certificate)}];const importing=app.nodes['certificate-file'].emit('change');await sleep(0);app.nodes.title.value='Newer than failed import';app.nodes.title.emit('input');const status=app.nodes.status.textContent;release({_error:'Duplicate JSON field: status'});await importing;
  assert.equal(app.evaluate('state.design.title'),'Newer than failed import');assert.equal(app.nodes.status.textContent,status);assert.equal(app.evaluate('state.certificate'),null);assert.equal(app.nodes['export-certificate'].disabled,true);assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);
});
test('slow first initialization exposes no editable reference or executable old design',async()=>{
  let release;const app=setup(new Promise(resolve=>release=resolve));assert.equal(app.nodes.vref.disabled,true);assert.equal(app.nodes.title.disabled,true);assert.equal(app.nodes.analyze.disabled,true);app.nodes.analyze.click();assert.equal(app.requests.filter(r=>r.url==='/api/jobs').length,0);release(copy(certificate.design));await sleep(0);assert.equal(app.nodes.vref.disabled,false);assert.equal(app.nodes.title.disabled,false);assert.equal(app.nodes.analyze.disabled,false);assert.equal(app.evaluate('state.design.vref'),'1');
});
