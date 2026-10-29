"""Advanced Studio v0.13.6: functional graph-editor behaviors in a Node VM."""
import http.client
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from lulwa_virtual_printer import hub


ROOT = Path(hub.__file__).with_name("ui")


def test_editor_assets_load_and_have_accessible_ports(tmp_path):
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    studio = (ROOT / "studio.js").read_text(encoding="utf-8")
    engine = (ROOT / "studio_editor.js").read_text(encoding="utf-8")
    assert 'src="/studio_editor.js"' in html
    assert html.index('src="/studio.js"') < html.index('src="/studio_editor.js"')
    for part in ('data-flow-port="in"', 'data-flow-port="out"', 'aria-label="Connect',
                 "flow-link-selected", "flow-debug:", "flow-undo", "flow-redo"):
        assert part in studio
    for part in ("flowLinkError", "flowUndoEdit", "flowStatusForNode", "flowWirePreview",
                 "pointerdown", "pointermove", "pointerup", "keydown"):
        assert part in engine
    node = shutil.which("node")
    if node:
        for path in (ROOT / "studio.js", ROOT / "studio_editor.js"):
            result = subprocess.run([node, "--check", str(path)], capture_output=True,
                                    text=True, timeout=30)
            assert result.returncode == 0, result.stderr


def test_studio_editor_graph_undo_redo_and_diagnostics_in_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    # Evaluate the actual scripts in their browser loading order. No fake graph
    # implementation: calls below exercise production functions.
    runner = r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const listeners={};
const ctx={
 structuredClone, Math, Object, JSON, Map, Set, console,
 document:{addEventListener:(name,fn)=>{(listeners[name]??=[]).push(fn)},
           elementFromPoint:()=>null},
 state:{devices:[],studio:{runs:[],workflows:[]}},
 route:"studio", E:()=>null,draw:()=>{},
 clean:x=>String(x), button:(n,a)=>'<button>'+n+":"+a+'</button>',
 showToast:(msg,bad)=>{ctx.lastToast={msg,bad}},
 lastToast:null
};
vm.createContext(ctx);
for(const name of ["studio.js","studio_editor.js"])
 vm.runInContext(fs.readFileSync(process.argv[1]+"/"+name,"utf8"),ctx,{filename:name});
const execute=script=>vm.runInContext(script,ctx);
execute('flowDraft={id:"saved-id",revision:7,name:"QA",nodes:['+
 '{id:"A",type:"start",x:10,y:10,config:{}},'+
 '{id:"B",type:"barcode",x:240,y:10,config:{value:"SKU"}},'+
 '{id:"C",type:"output",x:520,y:10,config:{}}],'+
 'edges:[{source:"A",target:"B"},{source:"B",target:"C"}]};flowSelected="B";flowResetHistory()');
assert.equal(execute('flowLinkError("B","A")'),"Start nodes cannot receive connections");
assert.equal(execute('flowLinkError("C","B")'),"Output nodes cannot send connections");
assert.equal(execute('flowLinkError("B","B")'),"A node cannot connect to itself");
assert.equal(execute('flowLinkError("A","B")'),"Connection already exists");
assert.equal(execute('flowLinkError("A","C")'),null);
execute('flowLinkNodes("A","C")');
assert.equal(execute('flowDraft.edges.length'),3);
assert.equal(execute('flowUndoStack.length'),1);
execute('flowUndoEdit()');
assert.equal(execute('flowDraft.edges.length'),2);
assert.equal(execute('flowRedoStack.length'),1);
execute('flowUndoEdit(true)');
assert.equal(execute('flowDraft.edges.length'),3);
execute('flowUndoEdit()');
execute('flowMutation(()=>flowDraft.nodes.find(n=>n.id==="B").x=270)');
assert.equal(execute('flowRedoStack.length'),0);
assert.equal(execute('flowDraft.id'),"saved-id");
assert.equal(execute('flowDraft.revision'),7);
assert.equal(execute('flowDraft.nodes[1].x'),270);
execute('flowUndoEdit()');
assert.equal(execute('flowDraft.nodes[1].x'),240);
execute('flowMutation(()=>{flowDraft.nodes.push({id:"D",type:"barcode",x:400,y:100,config:{value:"X"}});flowDraft.edges.push({source:"B",target:"D"})})');
assert.equal(execute('flowLinkError("D","B")'),"Connections cannot create cycles");
execute('flowUndoEdit()');
assert.equal(execute('flowDraft.nodes.length'),3);
const markup=execute('flowCard(flowDraft.nodes[1])');
assert(markup.includes('data-flow-port="in"'));
assert(markup.includes('data-flow-port="out"'));
const start=execute('flowCard(flowDraft.nodes[0])');
assert(!start.includes('data-flow-port="in"'));
const output=execute('flowCard(flowDraft.nodes[2])');
assert(!output.includes('data-flow-port="out"'));
assert(execute('flowWireD(flowDraft.nodes[0],flowDraft.nodes[1])').startsWith("M198 55 C"));
const snapshot=execute('flowSnapshot()');
ctx.state.studio.runs=[{id:"old-run",workflow_id:"saved-id",status:"failed",
 workflow_snapshot:snapshot,steps:[
 {node_id:"A",status:"completed",detail:"started"},
 {node_id:"B",status:"failed",detail:"reader busy"},
 {node_id:"C",status:"skipped",detail:"upstream"}]}];
execute('flowDebugRunId="old-run"');
assert.equal(execute('flowStatusForNode("B").status'),"failed");
assert(execute('flowDebugPanel()').includes("reader busy"));
assert(execute('flowCard(flowDraft.nodes[1])').includes("flow-result-failed"));
execute('flowMutation(()=>flowDraft.nodes.find(n=>n.id==="B").x=320)');
assert.equal(execute('flowStatusForNode("B")'),null);
assert(execute('flowDebugPanel()').includes("highlights are hidden"));
execute('flowResetHistory()');
assert.equal(execute('flowUndoStack.length'),0);
execute('for(let i=0;i<45;i++)flowMutation(()=>{flowDraft.nodes[1].x++})');
assert.equal(execute('flowUndoStack.length'),40);
execute('for(let i=0;i<48;i++)flowDraft.edges.push({source:"A",target:"C"})');
assert.equal(execute('flowLinkError("A","C")'),"Maximum 48 connections reached");
console.log("Studio editor graph, history, port markup, and run diagnostic checks passed");
"""
    result = subprocess.run([node, "-e", runner, str(ROOT)], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout


def test_studio_editor_asset_is_served_by_authenticated_local_hub(tmp_path):
    server = hub.create_server(port=0, state_dir=tmp_path / "cfg",
                               output_dir=tmp_path / "out")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=12)
        client.request("GET", "/studio_editor.js")
        response = client.getresponse()
        content = response.read()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith("application/javascript")
        assert b"function flowUndoEdit" in content
        client.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
