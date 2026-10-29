/* Advanced Studio — local workflow graph editor.
 * Uses in-app fixtures or an explicitly started localhost scale adapter.
 */
let flowDraft=null,flowSelected=null,flowConnect=null,flowDragging=null,flowImportDoc=null;
const flowTypes={
  start:{label:"Start",icon:"▶",caption:"Local event trigger",color:"blue"},
  barcode:{label:"Barcode",icon:"▥",caption:"Sample barcode data",color:"indigo"},
  scale:{label:"Scale",icon:"⚖",caption:"Local weight fixture",color:"teal"},
  tcp_scale:{label:"TCP Scale",icon:"◎",caption:"Real localhost scale read",color:"teal"},
  serial_scale:{label:"Serial Scale",icon:"↔",caption:"Real local PTY weight read",color:"teal"},
  capture:{label:"Capture",icon:"▤",caption:"Printer / scanner → JPG",color:"purple"},
  output:{label:"Output",icon:"▧",caption:"Review run results",color:"green"}
};
const flowId=()=>("node_"+Math.random().toString(36).slice(2,10));
const flowList=()=>state.studio?.workflows||[];
const flowRuns=()=>state.studio?.runs||[];
const flowDeviceOptions=(k,id)=>state.devices.filter(d=>k==="tcp_scale"?d.category==="scale"&&d.transport==="network":k==="serial_scale"?d.category==="scale"&&d.transport==="serial":k==="scale"?d.category==="scale":["brother","zebra","scanner"].includes(d.preset)).map(d=>
  '<option value="'+clean(d.id)+'" '+(id===d.id?"selected":"")+'>'+clean(d.name)+'</option>').join("");
function flowTemplate(){
 const brother=state.devices.find(d=>d.preset==="brother"),zebra=state.devices.find(d=>d.preset==="zebra"),scale=state.devices.find(d=>d.category==="scale");
 const nodes=[
 {id:flowId(),type:"start",x:38,y:195,config:{}},
 {id:flowId(),type:"barcode",x:270,y:195,config:{value:"TEST-1001"}}
 ];
 if(scale)nodes.push({id:flowId(),type:"scale",x:510,y:195,config:{device_id:scale.id,gross_kg:1.25,tare_kg:0,unit:"lb",stable:true}});
 const printers=[brother,zebra].filter(Boolean);
 for(let index=0;index<printers.length;index++)
   nodes.push({id:flowId(),type:"capture",x:740,y:80+index*170,config:{device_id:printers[index].id,title:index===0?"Studio Packing Slip":"Studio Shipping Label"}});
 nodes.push({id:flowId(),type:"output",x:1000,y:195,config:{}});
 const input=scale?nodes[2]:nodes[1],output=nodes[nodes.length-1];
 const edges=[{source:nodes[0].id,target:nodes[1].id}];
 if(scale)edges.push({source:nodes[1].id,target:nodes[2].id});
 if(printers.length){
  for(const p of nodes.filter(n=>n.type==="capture")){
   edges.push({source:input.id,target:p.id},{source:p.id,target:output.id});
  }
 }else edges.push({source:input.id,target:output.id});
 return {name:"Shipping Station — Local QA",nodes,edges};
}
function flowOpen(id){
 flowDraft=structuredClone(flowList().find(x=>x.id===id)||flowTemplate());
 flowSelected=flowDraft.nodes[0]?.id||null;flowConnect=null;draw();
}
function flowSync(){
 if(!flowDraft)return;
 const name=E("flow-title");
 if(name)flowDraft.name=name.value;
 const node=flowDraft.nodes.find(x=>x.id===flowSelected);
 if(!node)return;
 const cfg=node.config;
 const read=(id)=>E(id)?.value;
 if(node.type==="barcode"&&E("flow-barcode"))cfg.value=read("flow-barcode");
 if((node.type==="tcp_scale"||node.type==="serial_scale")&&E("flow-device"))cfg.device_id=read("flow-device");
 if(node.type==="capture"){
   if(E("flow-device"))cfg.device_id=read("flow-device");
   if(E("flow-job-title"))cfg.title=read("flow-job-title");
 }
 if(node.type==="scale"){
   if(E("flow-device"))cfg.device_id=read("flow-device");
   if(E("flow-gross"))cfg.gross_kg=Number(read("flow-gross"));
   if(E("flow-tare"))cfg.tare_kg=Number(read("flow-tare"));
   if(E("flow-unit"))cfg.unit=read("flow-unit");
   if(E("flow-stable"))cfg.stable=read("flow-stable")==="true";
 }
}
function flowCard(n){
 const t=flowTypes[n.type];
 const d=state.devices.find(x=>x.id===n.config?.device_id);
 const subtitle=d?d.name:n.type==="barcode"?(n.config.value||"Test data"):
     (n.type==="scale"||n.type==="tcp_scale"||n.type==="serial_scale")?"Choose a saved scale":n.type==="capture"?"Choose a saved printer":"Local in-app step";
 return '<div class="flow-node '+t.color+(flowSelected===n.id?" selected":"")+'" data-flow-node="'+clean(n.id)+'" style="left:'+n.x+'px;top:'+n.y+'px">'+
 '<div class="flow-grab" role="button" tabindex="0" aria-label="Select '+clean(t.label)+' node" data-flow-drag="'+clean(n.id)+'" data-action="flow-select:'+clean(n.id)+'"><span class="flow-node-icon">'+t.icon+'</span><span><b>'+t.label+'</b><small>'+clean(t.caption)+'</small></span><span class="flow-drag-handle" aria-hidden="true">⠿</span></div>'+
 '<div class="flow-node-foot">'+clean(subtitle)+'</div><span class="flow-port in" aria-hidden="true"></span><span class="flow-port out" aria-hidden="true"></span></div>';
}
function flowWires(){
 if(!flowDraft)return "";
 const coords=new Map(flowDraft.nodes.map(n=>[n.id,n]));
 return '<svg class="flow-wires" viewBox="0 0 1260 620" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="flow-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="none" stroke="#668ab9" stroke-width="1.4"/></marker></defs>'+
 flowDraft.edges.map(e=>{
   const a=coords.get(e.source),b=coords.get(e.target);
   if(!a||!b)return "";
   const x=a.x+188,y=a.y+45,tx=b.x,ty=b.y+45;
   const bend=Math.max(45,Math.abs(tx-x)*.48);
   return '<path data-wire="'+clean(e.source)+'-'+clean(e.target)+'" d="M'+x+' '+y+' C'+(x+bend)+' '+y+' '+(tx-bend)+' '+ty+' '+tx+' '+ty+'" fill="none" stroke="#658cba" stroke-width="2.3" marker-end="url(#flow-arrow)"/>';
 }).join("")+'</svg>';
}
function flowNodeInspector(){
 const n=flowDraft?.nodes.find(x=>x.id===flowSelected);
 if(!n)return '<div class="flow-inspector-empty">Select a node to configure it. To connect nodes, choose a source and select <b>Connect from here</b>.</div>';
 const t=flowTypes[n.type],c=n.config||{};
 let fields='<p class="small">This node runs entirely inside Devices Simulator. It does not register physical hardware.</p>';
 if(n.type==="barcode")fields='<label class="field"><span>Sample barcode value</span><input id="flow-barcode" maxlength="80" value="'+clean(c.value||"TEST-1001")+'"></label><p class="small">Fixture data only — no keyboard/HID events.</p>';
 if(n.type==="capture"||n.type==="scale"||n.type==="tcp_scale"||n.type==="serial_scale"){
  fields='<label class="field"><span>Saved '+((n.type==="scale"||n.type==="tcp_scale"||n.type==="serial_scale")?"scale":"printer / scanner")+'</span><select id="flow-device">'+flowDeviceOptions(n.type,c.device_id)+'</select></label>';
  if(n.type==="tcp_scale") fields+='<p class="small">Uses a real localhost TCP socket. Activate this scale in Connections first; no physical hardware or remote host is accessed.</p>';
  if(n.type==="serial_scale") fields+='<p class="small">Opens an activated local macOS/Linux PTY from Connections. Stop SUB streaming before running. Not USB or Windows COM.</p>';
  if(n.type==="capture") fields+='<label class="field"><span>Capture title</span><input id="flow-job-title" maxlength="80" value="'+clean(c.title||"Studio Capture")+'"></label><p class="small">Produces local JPGs. Bypasses CUPS and real OS queues.</p>';
  if(n.type==="scale") fields+='<div class="grid two"><label class="field"><span>Gross kg</span><input type="number" min="0" step="0.001" id="flow-gross" value="'+clean(c.gross_kg??1.25)+'"></label><label class="field"><span>Tare kg</span><input type="number" min="0" step="0.001" id="flow-tare" value="'+clean(c.tare_kg??0)+'"></label><label class="field"><span>Unit</span><select id="flow-unit">'+["kg","lb","g","oz"].map(u=>'<option '+(c.unit===u?"selected":"")+'>'+u+'</option>').join("")+'</select></label><label class="field"><span>Stability</span><select id="flow-stable"><option value="true" '+(c.stable!==false?"selected":"")+'>Stable</option><option value="false" '+(c.stable===false?"selected":"")+'>Unstable</option></select></label></div><p class="small">Tare-adjusted reading; no physical USB/BLE/network request.</p>';
 }
 const edges=flowDraft.edges.filter(e=>e.source===n.id||e.target===n.id);
 return '<div class="flow-inspector-title"><span class="flow-node-icon">'+t.icon+'</span><div><strong>'+t.label+'</strong><small>'+clean(n.id)+'</small></div></div>'+fields+
 '<div class="flow-inspector-actions">'+button(flowConnect===n.id?"Choose destination…":"Connect from here","flow-link:"+n.id,"primary")+
 button("Delete node","flow-remove:"+n.id,"danger",n.type==="start"||n.type==="output")+'</div>'+
 (edges.length?'<h3 class="flow-subtitle">Connections</h3>'+edges.map((e,i)=>'<div class="flow-connection"><span>'+clean(e.source===n.id?"→ "+e.target:e.source+" →")+'</span>'+button("Remove","flow-unlink:"+flowDraft.edges.indexOf(e),"")+'</div>').join(""):'<p class="small">No connections yet.</p>');
}
function flowImportBindings(){
 const refs=new Map();
 for(const node of flowImportDoc?.workflow?.nodes||[]){
  const id=node?.config?.device_id;
  if(typeof id==="string"&&!refs.has(id))refs.set(id,{id,type:node.type});
 }
 return [...refs.values()];
}
function flowImportCandidates(type){
 return state.devices.filter(d=>type==="tcp_scale"?d.category==="scale"&&d.transport==="network":
   type==="serial_scale"?d.category==="scale"&&d.transport==="serial":
   type==="scale"?d.category==="scale":
   type==="capture"?["office_printer","label_printer","scanner"].includes(d.category):false);
}
function flowImportPanel(){
 if(!flowImportDoc)return "";
 const refs=flowImportBindings();
 const mappings=refs.map((ref,i)=>{
  const candidates=flowImportCandidates(ref.type);
  return '<label class="field"><span>'+clean(ref.type)+' · original device '+clean(ref.id)+'</span>'+
    '<select id="flow-map-'+i+'"><option value="">Choose a compatible local device</option>'+
    candidates.map(d=>'<option value="'+clean(d.id)+'" '+(d.id===ref.id?"selected":"")+'>'+clean(d.name)+' ('+clean(d.transport)+')</option>').join("")+
    '</select></label>';
 }).join("");
 return '<div class="card" style="padding:22px"><h2>Import workflow JSON</h2>'+
  '<p>Workflow: <strong>'+clean(flowImportDoc.workflow.name)+'</strong></p>'+
  '<p class="small">Map imported device IDs to compatible saved local profiles. Import creates a NEW workflow and never activates connections.</p>'+
  mappings+(refs.length?'':'<p class="small">No device mappings needed.</p>')+
  '<div class="row wrap">'+button("Import as new workflow","flow-import-apply","primary")+
  button("Cancel","flow-import-cancel")+'</div></div>';
}
function flowHistory(){
 if(!flowDraft?.id)return '<p class="small">Save the workflow to enable execution history.</p>';
 const records=flowRuns().filter(r=>r.workflow_id===flowDraft.id).slice(0,8);
 if(!records.length)return '<p class="small">No runs yet. Save and use <b>Run locally</b>.</p>';
 return records.map(r=>'<details class="flow-run"><summary><span class="flow-status '+r.status+'">'+clean(r.status)+'</span> '+clean(r.started_at.slice(0,19))+' <small>'+r.steps.length+' steps</small></summary>'+
 (r.workflow_snapshot?'<div class="row wrap">'+button("Replay snapshot","flow-replay:"+r.id)+'</div>':'<p class="small">Legacy run has no snapshot for replay.</p>')+
 r.steps.map(st=>'<div class="flow-run-step"><span class="flow-status '+clean(st.status)+'">'+clean(st.status)+'</span><b>'+clean(st.type)+'</b><small>'+clean(st.detail)+'</small>'+
 (st.job_id&&st.images?.length?'<a class="flow-artifact" href="/api/artifacts/'+encodeURIComponent(st.job_id)+'/'+encodeURIComponent(st.images[0])+'" target="_blank" rel="noopener noreferrer">View JPG ↗</a>':"")+'</div>').join("")+'</details>').join("");
}
function studioPage(){
 if(flowDraft&&flowDraft.id){
  const remote=flowList().find(f=>f.id===flowDraft.id);
  if(!remote)flowDraft=null;
 }
 const library='<div class="flow-library"><div class="flow-panel-head"><b>My workflows</b>'+button("+ New","flow-new","primary")+'</div>'+
 (flowList().length?flowList().map(w=>'<button class="flow-library-item '+(flowDraft?.id===w.id?"active":"")+'" data-action="flow-open:'+clean(w.id)+'"><b>'+clean(w.name)+'</b><small>'+w.nodes.length+' nodes · revision '+w.revision+'</small></button>').join(""):'<div class="flow-library-empty">No saved workflows yet. Start with a local test template.</div>')+
 '<div class="flow-library-bottom"><b>Workflow files</b>'+button("Import JSON","flow-import")+
 '<input id="flow-import-file" type="file" accept=".json,application/json" hidden>'+
 '<p class="small">Portable JSON · max 64 KB · remap devices locally</p><b>Templates</b>'+button("Shipping Station","flow-template")+button("External TCP Scale","flow-network-template")+button("External Serial Scale","flow-serial-template")+'<p class="small">Templates bind to existing saved fixtures.</p></div></div>';
 if(flowImportDoc)return heading("ADVANCED DEVICE STUDIO","Import a portable workflow","Choose compatible local device profiles before creating a new workflow.")+
 '<div class="flow-layout">'+library+'<div class="flow-workspace">'+flowImportPanel()+'</div></div>';
 if(!flowDraft)return heading("ADVANCED DEVICE STUDIO","Visual workflow builder","Connect local device fixtures and inspect each step. Nothing is sent to physical devices.")+
 '<div class="flow-layout">'+library+'<div class="flow-welcome"><div class="flow-welcome-symbol">◇</div><h2>Design a repeatable device workflow</h2><p>Connect sample barcode input, a simulated scale, one or more printer captures, and an output check. Every run produces auditable local results.</p>'+
 button("Create from template","flow-template","primary")+button("External TCP Scale","flow-network-template")+button("External Serial Scale","flow-serial-template")+' '+button("Blank workflow","flow-new")+'</div></div>';
 const chosen=flowDraft.nodes.find(n=>n.id===flowSelected);
 const buttons='<div class="row wrap">'+button("Save","flow-save","primary")+button("Run locally","flow-run","",false)+button("Duplicate","flow-duplicate")+button("Export JSON","flow-export","",!flowDraft.id)+button("Delete","flow-delete","danger",!flowDraft.id)+'</div>';
 return heading("ADVANCED DEVICE STUDIO","Visual workflow builder","Editable DAG · local fixtures and opt-in TCP/serial scale adapters",badge("Local-only engine","green"))+
 '<div class="flow-layout">'+library+
 '<section class="flow-workspace"><div class="flow-toolbar"><label class="field"><span>Workflow name</span><input id="flow-title" maxlength="80" value="'+clean(flowDraft.name)+'"></label>'+
 '<div class="row wrap">'+buttons+'</div></div>'+
 '<div class="flow-add"><span>Add a node:</span>'+Object.entries(flowTypes).map(([k,v])=>
 button(v.icon+" "+v.label,"flow-add:"+k,"",k==="start"&&flowDraft.nodes.some(n=>n.type==="start"))).join("")+'</div>'+
 (flowConnect?'<div class="notice">Connecting from <b>'+clean(flowConnect)+'</b>. Click another node as the destination. '+button("Cancel","flow-link-cancel")+'</div>':"")+
 '<div class="flow-canvas-viewport"><div class="flow-canvas" id="flow-canvas">'+flowWires()+flowDraft.nodes.map(flowCard).join("")+'</div></div>'+
 '<div class="flow-editor-footer">Drag a node by its header · Select a node to configure · Link nodes with Connect from here · Save before running.</div>'+
 '<div class="flow-history"><h2>Run history</h2>'+flowHistory()+'</div></section>'+
 '<aside class="flow-inspector card"><h2>Node inspector</h2>'+flowNodeInspector()+
 '<div class="flow-safety"><b>Simulation boundary</b><p>Runs use local fixtures and existing localhost TCP/PTY scale endpoints. No drivers, physical USB/BLE, Windows COM, remote IPs or OS print jobs.</p></div></aside></div>';
}
async function flowSaveDraft(){
 flowSync();
 if(!flowDraft)throw Error("Create a workflow first");
 const saved=await post("/api/studio/workflows/save",flowDraft);
 flowDraft=structuredClone(saved.workflow);
 await refresh();
 return saved.workflow;
}
async function studioAction(k){
 try{
  if(k==="flow-import"){E("flow-import-file")?.click();return}
  if(k==="flow-import-cancel"){flowImportDoc=null;draw();return}
  if(k==="flow-import-apply"){
   if(!flowImportDoc)return;
   const mapping={};
   for(const [i,ref] of flowImportBindings().entries()){
    const chosen=E("flow-map-"+i)?.value;
    if(!chosen)return showToast("Select a compatible local device for every imported profile",true);
    mapping[ref.id]=chosen;
   }
   const result=await post("/api/studio/workflows/import",{document:flowImportDoc,device_map:mapping});
   flowImportDoc=null;await refresh();flowOpen(result.workflow.id);
   showToast("Workflow imported as a new copy");return;
  }
  if(k==="flow-network-template"){
   const d=state.devices.find(x=>x.category==="scale"&&x.transport==="network");
   if(!d)return showToast("Create a Network scale profile first",true);
   const nodes=[{id:flowId(),type:"start",x:40,y:190,config:{}},
     {id:flowId(),type:"tcp_scale",x:330,y:190,config:{device_id:d.id}},
     {id:flowId(),type:"output",x:650,y:190,config:{}}];
   flowDraft={name:"External TCP Scale QA",nodes,
     edges:[{source:nodes[0].id,target:nodes[1].id},
            {source:nodes[1].id,target:nodes[2].id}]};
   flowSelected=nodes[1].id;flowConnect=null;draw();return;
  }
  if(k==="flow-serial-template"){
   const d=state.devices.find(x=>x.category==="scale"&&x.transport==="serial");
   if(!d)return showToast("Create an RS-232 / serial scale profile first",true);
   const nodes=[{id:flowId(),type:"start",x:40,y:190,config:{}},
     {id:flowId(),type:"serial_scale",x:330,y:190,config:{device_id:d.id}},
     {id:flowId(),type:"output",x:650,y:190,config:{}}];
   flowDraft={name:"External Serial Scale QA",nodes,
     edges:[{source:nodes[0].id,target:nodes[1].id},
            {source:nodes[1].id,target:nodes[2].id}]};
   flowSelected=nodes[1].id;flowConnect=null;draw();return;
  }
  if(k==="flow-new"||k==="flow-template"){
   flowDraft=k==="flow-template"?flowTemplate():{name:"Untitled Workflow",nodes:[
    {id:flowId(),type:"start",x:70,y:220,config:{}},
    {id:flowId(),type:"output",x:440,y:220,config:{}}],edges:[]};
   flowSelected=flowDraft.nodes[0].id;flowConnect=null;draw();return;
  }
  if(k.startsWith("flow-open:")){flowOpen(k.slice(10));return}
  if(!flowDraft)return;
  flowSync();
  if(k==="flow-save"){await flowSaveDraft();showToast("Workflow saved");return}
  if(k==="flow-export"){
   if(!flowDraft.id)return showToast("Save the workflow before exporting",true);
   const result=await post("/api/studio/workflows/export",{id:flowDraft.id});
   const blob=new Blob([JSON.stringify(result.document,null,2)],{type:"application/json"});
   const url=URL.createObjectURL(blob);
   const link=document.createElement("a");
   link.href=url;link.download=(flowDraft.name.toLowerCase().replace(/[^a-z0-9]+/g,"-").slice(0,48)||"workflow")+".studio.json";
   document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
   showToast("Workflow JSON exported");return;
  }
  if(k.startsWith("flow-replay:")){
   if(!flowDraft.id)return;
   if(!confirm("Replay the saved graph snapshot? This starts a NEW run against current local fixtures, can produce NEW JPG files and new scale readings, and does not reproduce the earlier result."))return;
   const response=await post("/api/studio/workflows/replay",{id:flowDraft.id,run_id:k.slice(12),confirm:true});
   await refresh();showToast(response.run.status==="completed"?"Snapshot replay completed":"Replay has failed/skipped steps",response.run.status!=="completed");return;
  }
  if(k==="flow-run"){
   const saved=await flowSaveDraft();
   if(!confirm("Run this workflow against local fixtures? Printer/scan steps will create JPG files. TCP/serial nodes will contact previously activated local scale endpoints; no physical hardware or external hosts are accessed."))return;
   const response=await post("/api/studio/workflows/execute",{id:saved.id});
   await refresh();showToast(response.run.status==="completed"?"Local workflow completed":"Workflow had failed or skipped steps",response.run.status!=="completed");
   return;
  }
  if(k==="flow-delete"){
   if(!flowDraft.id||!confirm("Delete this saved workflow? Captured JPGs will remain."))return;
   await post("/api/studio/workflows/delete",{id:flowDraft.id});
   flowDraft=null;flowSelected=null;await refresh();showToast("Workflow deleted");return;
  }
  if(k==="flow-duplicate"){
   flowDraft=structuredClone(flowDraft);delete flowDraft.id;delete flowDraft.revision;delete flowDraft.created_at;delete flowDraft.updated_at;
   flowDraft.name=flowDraft.name+" (Copy)";draw();return;
  }
  if(k.startsWith("flow-add:")){
   const kind=k.slice(9);
   if(!flowTypes[kind])return;
   if(kind==="start"&&flowDraft.nodes.some(n=>n.type==="start"))return showToast("A workflow has one Start node",true);
   if(flowDraft.nodes.length>=24)return showToast("Maximum 24 nodes",true);
   const cfg={};
   if(kind==="barcode")cfg.value="TEST-1001";
   if(kind==="tcp_scale"){const d=state.devices.find(d=>d.category==="scale"&&d.transport==="network");if(!d)return showToast("Create a Network scale first",true);cfg.device_id=d.id}
   if(kind==="serial_scale"){const d=state.devices.find(d=>d.category==="scale"&&d.transport==="serial");if(!d)return showToast("Create an RS-232 / serial scale first",true);cfg.device_id=d.id}
   if(kind==="scale"){const d=state.devices.find(d=>d.category==="scale");if(!d)return showToast("Create a scale fixture first",true);Object.assign(cfg,{device_id:d.id,gross_kg:1.25,tare_kg:0,unit:"kg",stable:true})}
   if(kind==="capture"){const d=state.devices.find(d=>["brother","zebra","scanner"].includes(d.preset));if(!d)return showToast("Create a printer or scanner fixture first",true);Object.assign(cfg,{device_id:d.id,title:"Studio Capture"})}
   const n={id:flowId(),type:kind,x:70+(flowDraft.nodes.length%5)*220,y:75+Math.floor(flowDraft.nodes.length/5)*145,config:cfg};
   flowDraft.nodes.push(n);flowSelected=n.id;draw();return;
  }
  if(k.startsWith("flow-select:")){
   const nid=k.slice(12);if(!flowDraft.nodes.some(n=>n.id===nid))return;
   if(flowConnect&&flowConnect!==nid){
    if(!flowDraft.edges.some(e=>e.source===flowConnect&&e.target===nid))
      flowDraft.edges.push({source:flowConnect,target:nid});
    flowConnect=null;
   }
   flowSelected=nid;draw();return;
  }
  if(k==="flow-link-cancel"){flowConnect=null;draw();return}
  if(k.startsWith("flow-link:")){flowConnect=k.slice(10);showToast("Click the destination node");draw();return}
  if(k.startsWith("flow-unlink:")){flowDraft.edges.splice(Number(k.slice(12)),1);draw();return}
  if(k.startsWith("flow-remove:")){
   const nid=k.slice(12),n=flowDraft.nodes.find(n=>n.id===nid);
   if(!n||n.type==="start"||n.type==="output")return;
   flowDraft.nodes=flowDraft.nodes.filter(n=>n.id!==nid);
   flowDraft.edges=flowDraft.edges.filter(e=>e.source!==nid&&e.target!==nid);
   flowSelected=flowDraft.nodes[0]?.id||null;flowConnect=null;draw();return;
  }
 }catch(err){showToast(err.message,true)}
}
document.addEventListener("pointerdown",event=>{
 if(route!=="studio"||!flowDraft||!event.isPrimary)return;
 const header=event.target.closest("[data-flow-drag]");
 if(!header||event.target.closest("button, input, select"))return;
 const canvas=E("flow-canvas"),node=header.closest("[data-flow-node]");
 if(!canvas||!node)return;
 const rect=canvas.getBoundingClientRect();
 const record=flowDraft.nodes.find(x=>x.id===node.dataset.flowNode);
 if(!record)return;
 flowSync();
 flowDragging={id:record.id,node,pointer:event.pointerId,x:event.clientX,y:event.clientY,startX:record.x,startY:record.y};
 node.setPointerCapture(event.pointerId);
});
document.addEventListener("pointermove",event=>{
 if(!flowDragging||event.pointerId!==flowDragging.pointer||!flowDraft)return;
 const record=flowDraft.nodes.find(x=>x.id===flowDragging.id);if(!record)return;
 const nx=Math.max(0,Math.min(1060,Math.round(flowDragging.startX+event.clientX-flowDragging.x)));
 const ny=Math.max(0,Math.min(510,Math.round(flowDragging.startY+event.clientY-flowDragging.y)));
 record.x=nx;record.y=ny;flowDragging.node.style.left=nx+"px";flowDragging.node.style.top=ny+"px";
});
document.addEventListener("pointerup",event=>{
 if(!flowDragging||event.pointerId!==flowDragging.pointer)return;
 const record=flowDragging;flowDragging=null;
 const moved=Math.abs(event.clientX-record.x)+Math.abs(event.clientY-record.y)>7;
 if(!moved&&flowConnect&&flowConnect!==record.id){
   if(!flowDraft.edges.some(e=>e.source===flowConnect&&e.target===record.id))
     flowDraft.edges.push({source:flowConnect,target:record.id});
   flowConnect=null;
 }
 flowSelected=record.id;draw();
});

// Keyboard support for choosing nodes and completing a connection.
document.addEventListener("keydown",event=>{
 if(route!=="studio"||!event.target.matches(".flow-grab"))return;
 if(event.key!=="Enter"&&event.key!==" ")return;
 event.preventDefault();
 studioAction(event.target.dataset.action);
});

document.addEventListener("change",async event=>{
 if(event.target?.id!=="flow-import-file")return;
 const file=event.target.files?.[0];
 event.target.value="";
 if(!file)return;
 try{
  if(file.size>65536)throw Error("Workflow JSON exceeds 64 KB");
  const parsed=JSON.parse(await file.text());
  if(parsed?.format!=="devices-simulator-studio"||parsed?.version!==1||
     !parsed.workflow||!Array.isArray(parsed.workflow.nodes)||!Array.isArray(parsed.workflow.edges)||
     typeof parsed.workflow.name!=="string"||parsed.workflow.nodes.length>24)
   throw Error("Invalid or unsupported Studio workflow document");
  flowImportDoc=parsed;draw();
 }catch(err){showToast(err.message||"Invalid workflow JSON",true)}
});
