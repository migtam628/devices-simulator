"""Live Studio stepper UI: real shipped scripts in a Node VM."""
import shutil
import subprocess
from pathlib import Path
import pytest
from lulwa_virtual_printer import hub


def test_live_step_browser_controls_and_confirm_guard():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    root = Path(hub.__file__).with_name("ui")
    script = r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const calls=[],listeners={},responses={};
let approved=false;
const context={
 structuredClone,Map,Set,JSON,Math,Object,console,
 state:{devices:[],studio:{runs:[],workflows:[]}},
 route:"studio",E:()=>null,draw:()=>{},clean:value=>String(value),
 button:(text,action)=>'<button data-action="'+action+'">'+text+'</button>',
 showToast:()=>{},confirm:()=>approved,
 document:{addEventListener:(name,fn)=>(listeners[name]??=[]).push(fn),
           elementFromPoint:()=>null},
 refresh:async()=>{},
 post:async(url,data)=>{calls.push({url,data});
  if(url==="/api/studio/debug/start")return {session:{session_id:"session",workflow_id:"saved",
    workflow_revision:1,status:"paused",expected_step:0,total_steps:2,
    next_node:{id:"start",type:"start",requires_confirmation:false},steps:[]}};
  if(url==="/api/studio/debug/step"){
   if(data.expected_step===0)return {result:{finished:false,status:"paused",
    executed:{node_id:"start",type:"start",status:"completed",detail:"started"},
    session:{session_id:"session",workflow_id:"saved",workflow_revision:1,
     expected_step:1,total_steps:2,next_node:{id:"capture",type:"capture",
     requires_confirmation:true},steps:[{node_id:"start",type:"start",status:"completed",detail:"started"}]}}};
   return {result:{finished:true,status:"completed",session:null}};
  }
  if(url==="/api/studio/debug/status")return {session:null};
  if(url==="/api/studio/debug/cancel")return {run:{status:"cancelled"}};
  throw new Error("Unexpected call "+url);
 }
};
vm.createContext(context);
for(const name of ["studio.js","studio_editor.js","studio_debugger.js"])
 vm.runInContext(fs.readFileSync(process.argv[1]+"/"+name,"utf8"),context,{filename:name});
const e=str=>vm.runInContext(str,context);
(async()=>{
 e('flowDraft={id:"saved",revision:1,name:"UI",nodes:[{id:"start",type:"start",x:30,y:50,config:{}},'+
 '{id:"capture",type:"capture",x:260,y:50,config:{device_id:"printer",title:"label"}},'+
 '{id:"output",type:"output",x:500,y:50,config:{}}],edges:[]};');
 e('flowSaveDraft=async()=>({id:"saved",revision:1})');
 assert(e('flowLivePanel()').includes("Start paused session"));
 await e('flowLiveAction("flow-live-start")');
 assert.equal(calls.length,0); // not confirmed
 approved=true;
 await e('flowLiveAction("flow-live-start")');
 assert.equal(calls[0].url,"/api/studio/debug/start");
 assert(e('flowLivePanel()').includes("Execute next step"));
 await e('flowLiveAction("flow-live-step")');
 assert.equal(calls[1].data.expected_step,0);
 assert.equal(calls[1].data.confirm,false);
 assert(e('flowLivePanel()').includes("confirmation required"));
 approved=false;
 await e('flowLiveAction("flow-live-step")');
 assert.equal(calls.length,2); // denied
 approved=true;
 await e('flowLiveAction("flow-live-step")');
 assert.equal(calls[2].data.expected_step,1);
 assert.equal(calls[2].data.confirm,true);
 assert.equal(e('flowLiveSession'),null);
 console.log("Live UI explicit confirmations and step sequence verified");
})().catch(error=>{console.error(error);process.exit(1)});
"""
    result = subprocess.run([node, "-e", script, str(root)], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout


def test_live_ui_statically_exposes_controls():
    root = Path(hub.__file__).with_name("ui")
    content = (root / "studio_debugger.js").read_text(encoding="utf-8")
    studio = (root / "studio.js").read_text(encoding="utf-8")
    for term in ("flow-live-start", "flow-live-status", "flow-live-step", "flow-live-cancel",
                 "/api/studio/debug/start", "/api/studio/debug/step", "expected_step",
                 "requires_confirmation"):
        assert term in content
    assert "flowLivePanel()" in studio
