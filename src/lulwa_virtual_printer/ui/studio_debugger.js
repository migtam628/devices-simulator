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

/* v0.13.9 Live step runner: network actions only on user clicks.
 * Every single step is gated on the server and cannot be retried twice.
 */
let flowLiveSession=null;
function flowLivePanel(){
 const session=flowLiveSession;
 if(!session)return '<p class="small">A live step session uses an immutable SAVED workflow revision. Only your explicit Next step action runs one node. Scale reads and JPG captures require a separate confirmation.</p>'+
 '<div class="row wrap">'+button("Start paused session","flow-live-start","primary")+
 button("Recover active session","flow-live-status")+'</div>';
 if(session.workflow_id!==flowDraft?.id)return '<div class="notice">A live session exists for a different saved workflow. Open that workflow or cancel the session.</div>'+
 '<div class="row wrap">'+button("Recover session","flow-live-status")+button("Cancel session","flow-live-cancel","danger")+'</div>';
 const next=session.next_node;
 return '<div class="notice"><b>PAUSED — no background execution</b><p class="small">Saved workflow revision '+session.workflow_revision+
 ' · '+session.expected_step+' / '+session.total_steps+' steps completed. Session expires after 15 minutes of inactivity. Refresh requires Recover active session.</p></div>'+
 (next?'<p class="small"><b>Next:</b> '+clean(next.type)+' ('+clean(next.id)+')'+
 (next.requires_confirmation?' — confirmation required before local fixture/device effects':' — safe local graph operation')+'</p>':'')+
 '<div class="row wrap">'+button("Execute next step","flow-live-step","primary",!next)+
 button("Recover status","flow-live-status")+button("Cancel session","flow-live-cancel","danger")+'</div>'+
 '<div class="flow-inspection-list">'+session.steps.map((s,i)=>
 '<div class="flow-inspection-step"><b>'+(i+1)+'. '+clean(s.type)+'</b> <small>'+clean(s.status)+': '+clean(s.detail||"")+'</small>'+
 (s.selected_branch?'<small>Selected '+clean(s.selected_branch.toUpperCase())+'</small>':'')+
 (s.job_id&&s.images?.length?'<a href="/api/artifacts/'+encodeURIComponent(s.job_id)+'/'+encodeURIComponent(s.images[0])+
 '" target="_blank" rel="noopener noreferrer">View JPG</a>':'')+
 '</div>').join("")+'</div>';
}
async function flowLiveAction(action){
 if(action==="flow-live-status"){
  const response=await post("/api/studio/debug/status",{});
  flowLiveSession=response.session;draw();return;
 }
 if(action==="flow-live-start"){
  if(!flowDraft)return;
  flowSync();
  if(!confirm("Start a paused manual execution using a saved workflow? No nodes will run until you select Execute next step. Subsequent steps can create JPGs or contact active local scale endpoints."))return;
  const saved=await flowSaveDraft();
  const response=await post("/api/studio/debug/start",{id:saved.id,revision:saved.revision});
  flowLiveSession=response.session;draw();showToast("Paused session created; no steps executed");
  return;
 }
 if(!flowLiveSession)return showToast("Recover the active session first",true);
 if(action==="flow-live-cancel"){
  if(!confirm("Cancel this paused session? Already executed steps and any JPG captures cannot be undone. Partial results will remain in run history."))return;
  const response=await post("/api/studio/debug/cancel",{session_id:flowLiveSession.session_id});
  flowLiveSession=null;await refresh();showToast("Debug session cancelled; partial run recorded");return;
 }
 if(action==="flow-live-step"){
  const current=flowLiveSession.next_node;
  if(!current)return;
  const needs=current.requires_confirmation;
  const approved=needs?confirm("Execute this "+current.type+" step now? It may update a local scale fixture, read an active local TCP/PTY scale adapter, or create NEW JPG files. This action cannot be undone."):false;
  if(needs&&!approved)return;
  const response=await post("/api/studio/debug/step",{
   session_id:flowLiveSession.session_id,
   expected_step:flowLiveSession.expected_step,
   confirm:needs?true:false
  });
  flowLiveSession=response.result.session;
  if(response.result.finished){
   await refresh();
   showToast(response.result.status==="completed"?"Step execution completed":"Step execution finished with failures",
     response.result.status!=="completed");
  }else{
   draw();
   if(response.result.executed.status==="failed")showToast("Step failed — downstream dependents may be skipped",true);
  }
 }
}
