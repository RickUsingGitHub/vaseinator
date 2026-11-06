// Exercise the actual state functions with a delayed Python worker and minimal presentation stubs.
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=readFileSync('web/app.js','utf8');
const context=vm.createContext({console,setTimeout:()=>0,clearTimeout(){}});
vm.runInContext(`
let C={printer_keys:['line_width']}, K={REAL_VASE:0,FAKE_VASE:1}, params={height:180,color1:'blue',line_width:.6,vase_mode:1};
let liveFrom=null,shown,reply,recoveryTimer=0;
const undoStack=[],redoStack=[],saved={};
const store={set(k,v){saved[k]=JSON.parse(JSON.stringify(v))},get(k){return saved[k]}};
function pushUndo(s){undoStack.push(s);redoStack.length=0}
function undoButtons(){} function status(){} function showProblem(e){throw new Error(e)}
function refreshSimple(){} function refreshAdvanced(){} function rebuild(){}
const helper={call(name,text,key,value){if(name==='shown')return Promise.resolve('[]');return new Promise(resolve=>{reply=()=>resolve(JSON.stringify({params:{...JSON.parse(text),[key]:JSON.parse(value)},shown:[]}))})}};
`+source.slice(source.indexOf('let queue ='),source.indexOf('function pushUndo'))+
source.slice(source.indexOf('function needsNormal'),source.indexOf('// ================================================================== building it'))+
source.slice(source.indexOf('function rememberPrinter'),source.indexOf('async function fitHead')),context);
const run=s=>vm.runInContext(s,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  run(`commit('height',200)`);await tick();run(`change({color1:'red'});reply()`);await run('queue');
  assert.equal(run('params.height'),200);assert.equal(run('params.color1'),'red');
  run(`commit('line_width',.8)`);await tick();run('reply()');await run('queue');
  run(source.slice(source.indexOf('  const printer = store.get'),source.indexOf('  $("loading").hidden = true;')));
  assert.equal(run('params.line_width'),.8);
  run('step(undoStack,redoStack)');await run('queue');assert.equal(run('params.line_width'),.6);assert.equal(run('saved.printer.line_width'),.6);
  run('step(redoStack,undoStack)');await run('queue');assert.equal(run('params.line_width'),.8);
  run(`commit('height',250)`);await tick();run('step(undoStack,redoStack);reply()');await run('queue');assert.equal(run('params.height'),200);
  run(`commit('height',260)`);await tick();run(`replace({height:99,color1:'green',line_width:.4,vase_mode:1});reply()`);await run('queue');assert.equal(run('params.height'),99);
  console.log('PASS: delayed edits, colours, reload, undo/redo and replacement ordering');
})().catch(e=>{console.error(e);process.exitCode=1});
