/* Advanced Studio editor helpers: local graph history, port linking, run diagnostics.
 * Does not start devices, send print jobs, or bypass backend graph validation.
 */
let flowUndoStack=[],flowRedoStack=[],flowWireDrag=null,flowDebugRunId=null;
const FLOW_HISTORY_LIMIT=40;

function flowSnapshot(){
 if(!flowDraft)return null;
 return structuredClone({name:flowDraft.name,nodes:flowDraft.nodes,edges:flowDraft.edges});
}
function flowResetHistory(){
 flowUndoStack=[];flowRedoStack=[];flowWireDrag=null;flowConnect=null;flowDebugRunId=null;
}
function flowCommit(before){
 if(!before||!flowDraft||JSON.stringify(before)===JSON.stringify(flowSnapshot()))return false;
 flowUndoStack.push(before);
 if(flowUndoStack.length>FLOW_HISTORY_LIMIT)flowUndoStack.shift();
 flowRedoStack=[];
 return true;
}
function flowUndoEdit(redo=false){
 if(!flowDraft)return false;
 flowSync();
 const from=redo?flowRedoStack:flowUndoStack,to=redo?flowUndoStack:flowRedoStack;
 if(!from.length)return false;
 to.push(flowSnapshot());
 if(to.length>FLOW_HISTORY_LIMIT)to.shift();
 Object.assign(flowDraft,structuredClone(from.pop()));
 flowWireDrag=null;flowConnect=null;
 if(!flowDraft.nodes.some(n=>n.id===flowSelected))flowSelected=flowDraft.nodes[0]?.id||null;
 draw();return true;
}
function flowMutation(update){
 const before=flowSnapshot();
 update();
 flowCommit(before);draw();
}
function flowLinkError(source,target){
 const nodes=new Map((flowDraft?.nodes||[]).map(n=>[n.id,n]));
 if(!nodes.has(source)||!nodes.has(target))return "Choose two existing nodes";
 if(source===target)return "A node cannot connect to itself";
 if(nodes.get(source).type==="output")return "Output nodes cannot send connections";
 if(nodes.get(target).type==="start")return "Start nodes cannot receive connections";
 if(flowDraft.edges.length>=48)return "Maximum 48 connections reached";
 if(flowDraft.edges.some(e=>e.source===source&&e.target===target))return "Connection already exists";
 const pending=[target],seen=new Set();
 while(pending.length){
  const current=pending.pop();
  if(current===source)return "Connections cannot create cycles";
  if(seen.has(current))continue;
  seen.add(current);
  for(const edge of flowDraft.edges)if(edge.source===current)pending.push(edge.target);
 }
 return null;
}
function flowLinkNodes(source,target){
 const error=flowLinkError(source,target);
 if(error){showToast(error,true);return false}
 flowConnect=null;
 flowMutation(()=>flowDraft.edges.push({source,target}));
 return true;
}
function flowSelectedRun(){
 const run=flowRuns().find(r=>r.id===flowDebugRunId&&r.workflow_id===flowDraft?.id);
 return run?.workflow_snapshot?run:null;
}
function flowRunMatchesDraft(run){
 if(!run||!flowDraft)return false;
 return JSON.stringify({name:flowDraft.name,nodes:flowDraft.nodes,edges:flowDraft.edges})===
        JSON.stringify({name:run.workflow_snapshot.name,nodes:run.workflow_snapshot.nodes,edges:run.workflow_snapshot.edges});
}
function flowStatusForNode(id){
 const run=flowSelectedRun();
 return flowRunMatchesDraft(run)?run.steps.find(step=>step.node_id===id):null;
}
function flowDebugPanel(){
 const run=flowSelectedRun();
 if(!run)return "";
 const counts={completed:0,failed:0,skipped:0};
 for(const step of run.steps)if(Object.prototype.hasOwnProperty.call(counts,step.status))counts[step.status]++;
 const matches=flowRunMatchesDraft(run);
 const chosen=run.steps.find(step=>step.node_id===flowSelected);
 return '<div class="flow-debug-panel"><div class="row wrap"><b>Run diagnostics</b>'+button("Clear","flow-debug-clear")+'</div>'+
 '<p class="small">Run '+clean(run.id.slice(0,12))+' · '+clean(run.status)+' · '+
 counts.completed+' completed / '+counts.failed+' failed / '+counts.skipped+' skipped</p>'+
 (matches?'<p class="small">Matching graph: green completed, red failed, gray skipped.</p>':
 '<p class="small">Graph differs from this historical run; highlights are hidden to avoid incorrect attribution.</p>')+
 (chosen&&matches?'<p class="small"><b>Selected step:</b> '+clean(chosen.status)+' — '+clean(chosen.detail||"No detail")+'</p>':'')+
 (run.steps.filter(step=>step.status==="failed").map(step=>
 '<p class="small"><b>Failure '+clean(step.node_id)+':</b> '+clean(step.detail||"No detail")+'</p>').join("")||
 '<p class="small">No failed steps recorded.</p>')+'</div>';
}
function flowWireD(source,target){
 const x=source.x+188,y=source.y+45,tx=target.x,ty=target.y+45;
 const bend=Math.max(45,Math.abs(tx-x)*.48);
 return 'M'+x+' '+y+' C'+(x+bend)+' '+y+' '+(tx-bend)+' '+ty+' '+tx+' '+ty;
}
function flowUpdateWires(){
 if(!flowDraft)return;
 const nodes=new Map(flowDraft.nodes.map(n=>[n.id,n]));
 for(const [i,edge] of flowDraft.edges.entries()){
  const path=E("flow-wire-"+i),a=nodes.get(edge.source),b=nodes.get(edge.target);
  if(path&&a&&b)path.setAttribute("d",flowWireD(a,b));
 }
}
function flowWirePreview(source,x,y){
 const canvas=E("flow-canvas"),path=E("flow-wire-preview");
 const node=flowDraft?.nodes.find(n=>n.id===source);
 if(!canvas||!path||!node)return;
 const rect=canvas.getBoundingClientRect();
 path.setAttribute("d",flowWireD(node,{x:x-rect.left,y:y-rect.top-45}));
}
document.addEventListener("pointerdown",event=>{
 if(route!=="studio"||!flowDraft||event.isPrimary===false)return;
 const port=event.target.closest('[data-flow-port="out"]');
 if(!port)return;
 flowSync();
 flowWireDrag={source:port.dataset.flowPortNode,pointer:event.pointerId,
               startX:event.clientX,startY:event.clientY};
});
document.addEventListener("pointermove",event=>{
 if(!flowWireDrag||event.pointerId!==flowWireDrag.pointer)return;
 flowWirePreview(flowWireDrag.source,event.clientX,event.clientY);
});
document.addEventListener("pointerup",event=>{
 if(!flowWireDrag||event.pointerId!==flowWireDrag.pointer)return;
 const active=flowWireDrag;flowWireDrag=null;
 const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-flow-port="in"]');
 if(target)flowLinkNodes(active.source,target.dataset.flowPortNode);
 else if(Math.hypot(event.clientX-active.startX,event.clientY-active.startY)>10)
  showToast("Drop on an input port, or click output then choose a destination",true);
 const path=E("flow-wire-preview");if(path)path.setAttribute("d","");
});
document.addEventListener("pointercancel",()=>{flowWireDrag=null;const p=E("flow-wire-preview");if(p)p.setAttribute("d","")});
document.addEventListener("keydown",event=>{
 if(route!=="studio"||!flowDraft||!(event.ctrlKey||event.metaKey)||event.altKey)return;
 if(event.target?.matches?.('input,textarea,select,[contenteditable="true"]'))return;
 const key=event.key.toLowerCase();
 if(key==="z"||key==="y"){
  event.preventDefault();
  flowUndoEdit(key==="y"||(key==="z"&&event.shiftKey));
 }
});
