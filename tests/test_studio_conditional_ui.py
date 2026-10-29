"""Studio condition templates and branch-port controls load and operate in JS runtime."""
from pathlib import Path
import shutil
import subprocess
import pytest
from lulwa_virtual_printer import hub


def test_studio_condition_frontend_node_runtime():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not available")
    root = Path(hub.__file__).with_name("ui")
    runner = r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const callbacks={};
const ctx={
 structuredClone,Math,JSON,Map,Set,Object,console,
 state:{devices:[{id:"scale-1",preset:"scale",category:"scale",name:"Sim Scale"}],
        studio:{runs:[],workflows:[]}},
 document:{addEventListener:(n,cb)=>(callbacks[n]??=[]).push(cb),elementFromPoint:()=>null},
 route:"studio",E:()=>null,draw:()=>{},clean:s=>String(s),
 button:(label,action)=>'<button>'+label+' '+action+'</button>',
 showToast:(message,bad)=>{ctx.toast={message,bad}}
};
vm.createContext(ctx);
for(const file of ["studio.js","studio_editor.js","studio_debugger.js"])
 vm.runInContext(fs.readFileSync(process.argv[1]+"/"+file,"utf8"),ctx);
const e=(s)=>vm.runInContext(s,ctx);
(async()=>{
 await e('studioAction("flow-weight-template")');
 assert.equal(e('flowDraft.nodes.length'),5);
 assert.equal(e('flowDraft.edges.filter(edge=>edge.branch).length'),2);
 assert.equal(e('flowDraft.nodes[2].type'),"condition");
 assert(e('flowCard(flowDraft.nodes[2])').includes('data-flow-port-branch="true"'));
 assert(e('flowCard(flowDraft.nodes[2])').includes('data-flow-port-branch="false"'));
 const curveTrue=e('flowWireD(flowDraft.nodes[2],flowDraft.nodes[3],"true")');
 const curveFalse=e('flowWireD(flowDraft.nodes[2],flowDraft.nodes[3],"false")');
 assert.notEqual(curveTrue,curveFalse);
 assert.equal(e('flowLinkError(flowDraft.nodes[2].id,flowDraft.nodes[4].id)'),"Connection already exists");
 e('flowMutation(()=>flowDraft.edges.pop())');
 const check=e('flowDraft.nodes[2].id'),no=e('flowDraft.nodes[4].id');
 assert.equal(e('flowLinkError('+JSON.stringify(check)+','+JSON.stringify(no)+',"false")'),null);
 assert(e('flowLinkNodes('+JSON.stringify(check)+','+JSON.stringify(no)+',"false")'));
 assert.equal(e('flowDraft.edges.filter(edge=>edge.branch==="false").length'),1);
 assert.equal(e('flowUndoStack.length'),2);
 e('flowUndoEdit()');
 assert.equal(e('flowDraft.edges.filter(edge=>edge.branch==="false").length'),0);
 e('flowUndoEdit(true)');
 assert.equal(e('flowDraft.edges.filter(edge=>edge.branch==="false").length'),1);
 await e('studioAction("flow-barcode-template")');
 assert.equal(e('flowDraft.nodes[1].type'),"barcode");
 assert.equal(e('flowDraft.nodes[2].config.field'),"barcode");
 const snapshot=e('flowSnapshot()');
 ctx.state.studio.runs=[{id:"inspect",workflow_id:"saved",status:"completed",workflow_snapshot:snapshot,
 steps:[{node_id:snapshot.nodes[2].id,type:"condition",status:"completed",decision:true,selected_branch:"true",detail:"Selected TRUE"},
 {node_id:snapshot.nodes[4].id,type:"output",status:"inactive",detail:"Not selected"}]}];
 e('flowDraft.id="saved";flowDebugRunId="inspect"');
 assert(e('flowDebugPanel()').includes("inactive"));
 assert.equal(e('flowStatusForNode(flowDraft.nodes[4].id).status'),"inactive");
 console.log("Condition UI graph and diagnostics verified");
})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run([node, "-e", runner, str(root)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
