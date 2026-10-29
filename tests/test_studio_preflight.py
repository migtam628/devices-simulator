"""v0.13.8 read-only Studio debugger and preflight regressions."""
import copy
import http.client
import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from lulwa_virtual_printer.hub import HubStore, create_server
from lulwa_virtual_printer.studio_engine import StudioManager


def flow(scale_id, printer_id):
    return {
        "name": "Safe preflight QA",
        "nodes": [
            {"id": "start", "type": "start", "config": {}},
            {"id": "scale", "type": "scale", "config": {
                "device_id": scale_id, "gross_kg": 2, "tare_kg": .25,
                "unit": "kg", "stable": True}},
            {"id": "decision", "type": "condition", "config": {
                "field": "weight", "operator": "gte", "value": 1.5}},
            {"id": "capture", "type": "capture", "config": {
                "device_id": printer_id, "title": "Packing Slip"}},
            {"id": "yes", "type": "output", "config": {}},
            {"id": "no", "type": "output", "config": {}},
        ],
        "edges": [
            {"source": "start", "target": "scale"},
            {"source": "scale", "target": "decision"},
            {"source": "decision", "target": "capture", "branch": "true"},
            {"source": "decision", "target": "no", "branch": "false"},
            {"source": "capture", "target": "yes"},
        ],
    }


def fixture(tmp_path):
    store = HubStore(tmp_path/"state", tmp_path/"out")
    scale = store.create_device({"preset": "scale", "name": "Preflight Scale"})
    printer = store.create_device({"preset": "brother", "name": "Preflight Printer"})
    studio = StudioManager(tmp_path/"state", store)
    return store, studio, scale, printer


def test_inspection_topological_branch_metadata_checkpoint_and_purity(tmp_path):
    store, studio, scale, printer = fixture(tmp_path)
    draft = flow(scale["id"], printer["id"])
    before_store = copy.deepcopy(store.list_devices())
    before_file = studio.path.read_bytes()
    result = studio.inspect(draft, checkpoints=["decision", "capture"])
    assert result["mode"] == "read_only_preflight"
    assert result["execution_performed"] is False
    assert result["node_count"] == 6 and result["edge_count"] == 5
    assert result["checkpoints"] == ["decision", "capture"]
    assert result["may_generate_jpgs_on_execution"] is True
    assert result["may_read_managed_adapters_on_execution"] is False
    plan = {step["node_id"]: step for step in result["steps"]}
    assert plan["decision"]["checkpoint"] is True
    assert plan["decision"]["condition"]["operator"] == "gte"
    assert {edge["branch"] for edge in plan["decision"]["outgoing"]} == {"true", "false"}
    assert plan["capture"]["may_mutate_local_state"] is True
    assert plan["scale"]["may_mutate_local_state"] is True
    assert plan["capture"]["requires_active_adapter"] is False
    assert plan["start"]["incoming"] == []
    assert "unknown until" in plan["decision"]["note"]
    assert store.list_jobs() == []
    assert store.list_devices() == before_store
    assert studio.snapshot()["runs"] == []
    assert studio.path.read_bytes() == before_file


@pytest.mark.parametrize("bad", [
    "bad", {}, {"name": "Bad", "nodes": [], "edges": []}
])
def test_invalid_graph_never_writes_or_calls_devices(tmp_path, bad):
    store, studio, *_ = fixture(tmp_path)
    original = studio.path.read_bytes()
    with pytest.raises(ValueError):
        studio.inspect(bad)
    assert store.list_jobs() == []
    assert studio.path.read_bytes() == original


@pytest.mark.parametrize("checkpoints", [
    "decision", ["missing"], ["decision","decision"],
    ["\nnewline"], [123], ["start"]*25
])
def test_invalid_checkpoints_rejected_without_state_changes(tmp_path, checkpoints):
    store, studio, scale, printer = fixture(tmp_path)
    original = studio.path.read_bytes()
    with pytest.raises(ValueError):
        studio.inspect(flow(scale["id"], printer["id"]), checkpoints=checkpoints)
    assert studio.path.read_bytes() == original
    assert store.list_jobs() == []


def test_adapter_warning_without_connections_and_no_activation(tmp_path):
    store, studio, scale, printer = fixture(tmp_path)
    network = store.create_device({"preset": "scale", "name": "Managed TCP Scale", "transport": "network"})
    draft = flow(scale["id"], printer["id"])
    draft["nodes"][1] = {"id": "scale", "type": "tcp_scale",
                         "config": {"device_id": network["id"]}}
    plan = studio.inspect(draft)
    assert plan["may_read_managed_adapters_on_execution"] is True
    scale_step = next(step for step in plan["steps"] if step["node_id"] == "scale")
    assert scale_step["requires_active_adapter"] is True
    assert "localhost" in scale_step["action"]
    assert not store.list_jobs()
    assert not studio.snapshot()["runs"]


def test_authenticated_preflight_http_without_mutating_history(tmp_path):
    server = create_server(port=0,state_dir=tmp_path/"state",output_dir=tmp_path/"out")
    scale = server.hub_store.create_device({"preset":"scale","name":"HTTP Preflight Scale"})
    printer = server.hub_store.create_device({"preset":"brother","name":"HTTP Preflight Printer"})
    work = threading.Thread(target=server.serve_forever,daemon=True)
    work.start()
    connection = http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=15)
    payload = json.dumps({"workflow":flow(scale["id"],printer["id"]),"checkpoints":["decision"]})
    try:
        connection.request("POST","/api/studio/workflows/inspect",payload,{"Content-Type":"application/json"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.request("POST","/api/studio/workflows/inspect",payload,{
            "Content-Type":"application/json","X-Devices-Token":server.hub_token})
        response = connection.getresponse()
        content=json.loads(response.read())
        assert response.status == 200
        assert content["inspection"]["execution_performed"] is False
        assert content["inspection"]["steps"][2]["checkpoint"] is True
        assert server.hub_studio.snapshot()["runs"] == []
        assert server.hub_store.list_jobs() == []
        connection.request("GET","/studio_debugger.js")
        response=connection.getresponse()
        script=response.read()
        assert response.status == 200
        assert b"flowInspectionAction" in script
        connection.request("GET","/")
        response=connection.getresponse()
        html=response.read()
        assert b'src="/studio_debugger.js"' in html
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        work.join(timeout=3)


def test_actual_studio_debugger_browser_script_in_node_vm():
    node=shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    root=Path(__file__).resolve().parents[1]/"src/lulwa_virtual_printer/ui"
    code=r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const calls=[],events={},ctx={
 structuredClone,Math,JSON,Object,Set,Map,console,
 state:{devices:[],studio:{workflows:[],runs:[]}},
 route:"studio", E:()=>null, draw:()=>{},
 clean:x=>String(x),button:(label,action)=>'<button>'+label+' '+action+'</button>',
 showToast:()=>{},
 document:{addEventListener:(name,handler)=>(events[name]??=[]).push(handler),elementFromPoint:()=>null},
 post:async(path,request)=>{
   calls.push({path,request});
   if(path!=="/api/studio/workflows/inspect")throw Error("Unexpected side-effect call");
   return {inspection:{mode:"read_only_preflight",execution_performed:false,
     node_count:3,edge_count:2,may_generate_jpgs_on_execution:false,
     may_read_managed_adapters_on_execution:false,steps:[
      {step:1,node_id:"start",type:"start",action:"local trigger",incoming:[],outgoing:[{source:"start",target:"barcode"}],checkpoint:false,may_mutate_local_state:false},
      {step:2,node_id:"barcode",type:"barcode",action:"barcode fixture",incoming:[{source:"start",target:"barcode"}],outgoing:[{source:"barcode",target:"output"}],checkpoint:false,may_mutate_local_state:false},
      {step:3,node_id:"output",type:"output",action:"inspect output",incoming:[{source:"barcode",target:"output"}],outgoing:[],checkpoint:false,may_mutate_local_state:false}
     ]}};
 }
};
vm.createContext(ctx);
for(const name of ["studio.js","studio_editor.js","studio_debugger.js"])
 vm.runInContext(fs.readFileSync(process.argv[1]+"/"+name,"utf8"),ctx,{filename:name});
const run=s=>vm.runInContext(s,ctx);
(async()=>{
 run('flowDraft={name:"Plan",nodes:[{id:"start",type:"start",x:40,y:40,config:{}},'+
 '{id:"barcode",type:"barcode",x:240,y:40,config:{value:"TEST"}},'+
 '{id:"output",type:"output",x:440,y:40,config:{}}],'+
 'edges:[{source:"start",target:"barcode"},{source:"barcode",target:"output"}]};flowSelected="start"');
 assert(run('flowInspectionPanel()').includes("does not execute"));
 await run('flowInspectionAction("flow-inspect")');
 assert.equal(calls.length,1);
 assert.equal(calls[0].path,"/api/studio/workflows/inspect");
 assert.equal(run('flowInspectionMatchesDraft()'),true);
 assert(run('flowInspectionPanel()').includes("no execution performed"));
 assert(run('flowCard(flowDraft.nodes[0])').includes("flow-inspection-active"));
 await run('flowInspectionAction("flow-inspect-next")');
 assert.equal(run('flowInspectionIndex'),1);
 assert.equal(run('flowSelected'),"barcode");
 await run('flowInspectionAction("flow-checkpoint:barcode")');
 assert.equal(run('flowInspectionCheckpoints.has("barcode")'),true);
 assert(run('flowInspectionPanel()').includes("Unmark"));
 await run('flowInspectionAction("flow-inspect-prev")');
 assert.equal(run('flowInspectionIndex'),0);
 run('flowMutation(()=>flowDraft.nodes[0].x=90)');
 assert.equal(run('flowInspectionMatchesDraft()'),false);
 assert(run('flowInspectionPanel()').includes("changed"));
 await run('flowInspectionAction("flow-inspect-next")');
 assert.equal(run('flowInspectionIndex'),0);
 await run('flowInspectionAction("flow-inspect")');
 assert.equal(calls.length,2);
 assert.equal(calls[1].request.checkpoints[0],"barcode");
 await run('flowInspectionAction("flow-inspect-clear")');
 assert.equal(run('flowInspection'),null);
 assert.equal(run('flowInspectionCheckpoints.size'),0);
 console.log("Read-only preflight and debugger navigation verified");
})().catch(err=>{console.error(err);process.exit(1)});
"""
    checked=subprocess.run([node,"-e",code,str(root)],capture_output=True,text=True,timeout=30)
    assert checked.returncode==0,checked.stderr+checked.stdout
