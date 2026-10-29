/* Advanced Studio v0.13.8 read-only preflight debugger.
 * This file never performs an execution, starts a device or writes local captures.
 * "Checkpoints" are review markers, not runtime pause/resume breakpoints.
 */
let flowInspection=null,flowInspectionSignature=null,flowInspectionIndex=0;
let flowInspectionCheckpoints=new Set();

function flowInspectionSteps(){
 return Array.isArray(flowInspection?.steps)?flowInspection.steps:null;
}
function flowInspectionMatchesDraft(){
 return !!(flowDraft&&flowInspection&&flowInspectionSignature===JSON.stringify(flowSnapshot()));
}
function flowInspectionPanel(){
 const steps=flowInspectionSteps();
 if(!steps)return '<p class="small">Inspect plan validates the current draft and shows the order of steps, dependencies, device-read warnings, and optional checkpoints. It does not execute the workflow or create JPGs.</p>';
 if(!flowInspectionMatchesDraft())return '<div class="notice">The workflow has changed since the last inspection. The old plan is no longer displayed. Use Inspect plan again to validate your edits.</div>';
 const current=steps[flowInspectionIndex]||steps[0];
 const counters=[flowInspection.node_count+' nodes',flowInspection.edge_count+' links',
  steps.filter(s=>s.may_mutate_local_state).length+' potential local effects'];
 const danger=(flowInspection.may_generate_jpgs_on_execution?'A real run may create local JPG files. ':'')+
   (flowInspection.may_read_managed_adapters_on_execution?'A real run may read previously activated local scale adapters. ':'');
 return '<div class="notice"><b>Read-only preflight — no execution performed</b><p class="small">'+
  counters.join(' · ')+'. '+clean(danger)+'Branch decisions are unknown until execution. Checkpoints only mark review locations.</p></div>'+
  '<div class="row wrap">'+button("Previous step","flow-inspect-prev","",flowInspectionIndex===0)+
  button("Next step","flow-inspect-next","",flowInspectionIndex>=steps.length-1)+
  button("Clear plan","flow-inspect-clear")+'</div>'+
  '<p class="small"><b>Inspecting step '+(flowInspectionIndex+1)+' / '+steps.length+':</b> '+
    clean(current.type)+' — '+clean(current.action)+'</p>'+
  '<p class="small"><b>Incoming:</b> '+clean(current.incoming.map(e=>e.source+(e.branch?' ['+e.branch+']':'')).join(', ')||'none')+
   ' · <b>Outgoing:</b> '+clean(current.outgoing.map(e=>e.target+(e.branch?' ['+e.branch+']':'')).join(', ')||'none')+'</p>'+
  (current.requires_active_adapter?'<p class="small">This step requires an already-active, device-bound local adapter at actual execution time.</p>':'')+
  '<div class="flow-inspection-list">'+steps.map((step,index)=>
   '<div class="flow-inspection-step '+(index===flowInspectionIndex?'active':'')+'">'+
    button("Step "+step.step,"flow-inspect-step:"+index)+(step.checkpoint||flowInspectionCheckpoints.has(step.node_id)?' <b>◆</b> ':'')+
    '<strong>'+clean(step.type)+'</strong><small>'+clean(step.action)+'</small>'+
    (step.may_mutate_local_state?'<small>Local effects on execution</small>':'')+
    button(flowInspectionCheckpoints.has(step.node_id)?"Unmark":"Mark","flow-checkpoint:"+clean(step.node_id))+
   '</div>').join('')+'</div>';
}
async function flowInspectionAction(action){
 if(action==="flow-inspect"){
  flowSync();
  if(!flowDraft)return;
  const signature=JSON.stringify(flowSnapshot());
  const response=await post("/api/studio/workflows/inspect",{
   workflow:{name:flowDraft.name,nodes:flowDraft.nodes,edges:flowDraft.edges},
   checkpoints:[...flowInspectionCheckpoints].filter(nid=>flowDraft.nodes.some(n=>n.id===nid))
  });
  flowInspection=response.inspection;
  flowInspectionSignature=signature;
  flowInspectionIndex=0;
  draw();
  showToast("Validated read-only plan; no devices or captures were run");
  return;
 }
 if(action==="flow-inspect-clear"){
  flowInspection=null;flowInspectionSignature=null;flowInspectionIndex=0;
  flowInspectionCheckpoints=new Set();draw();return;
 }
 if(!flowInspectionMatchesDraft()){
  showToast("Workflow changed — use Inspect plan to validate again",true);
  return;
 }
 const steps=flowInspectionSteps();
 if(!steps?.length)return;
 if(action==="flow-inspect-next")flowInspectionIndex=Math.min(steps.length-1,flowInspectionIndex+1);
 else if(action==="flow-inspect-prev")flowInspectionIndex=Math.max(0,flowInspectionIndex-1);
 else if(action.startsWith("flow-inspect-step:")){
  const index=Number(action.slice("flow-inspect-step:".length));
  if(!Number.isInteger(index)||index<0||index>=steps.length)return;
  flowInspectionIndex=index;
 }else if(action.startsWith("flow-checkpoint:")){
  const id=action.slice("flow-checkpoint:".length);
  if(!steps.some(s=>s.node_id===id))return;
  if(flowInspectionCheckpoints.has(id))flowInspectionCheckpoints.delete(id);
  else flowInspectionCheckpoints.add(id);
  for(const step of steps)step.checkpoint=flowInspectionCheckpoints.has(step.node_id);
 }else return;
 flowSelected=steps[flowInspectionIndex].node_id;
 draw();
}
