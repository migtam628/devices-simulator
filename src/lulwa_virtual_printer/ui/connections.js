/* Device Connections — localhost-only TCP scale endpoints.
   No USB HID/COM/BLE device is created by this page. */
const tcpListeners=()=>state.connections?.listeners||[];
const tcpListener=id=>tcpListeners().find(x=>x.device_id===id);
const tcpScaleDevices=()=>state.devices.filter(x=>x.category==="scale"&&x.transport==="network");

function connections(){
 const eligible=tcpScaleDevices();
 const running=tcpListeners();
 const overview='<div class="grid three">'+[
   ["Active TCP endpoints",running.length,"Listening on 127.0.0.1 only"],
   ["Connected clients",running.reduce((n,l)=>n+l.clients,0),"Current live sockets"],
   ["Handled commands",running.reduce((n,l)=>n+l.requests,0),"Scale read requests in this session"]
 ].map(([name,value,desc])=>'<div class="card conn-metric"><p class="muted">'+clean(name)+'</p><strong>'+clean(value)+'</strong><p class="small">'+clean(desc)+'</p></div>').join("")+'</div>';
 const options=eligible.map(d=>{
   const listener=tcpListener(d.id);
   const last=d.last_measurement||{};
   const title='<div class="cardhead"><h2>'+clean(d.name)+'</h2>'+badge(listener?.running?"TCP listener online":"Not listening",listener?.running?"green":"amber")+'</div>'+
     '<div class="conn-meta">'+clean(d.brand||"Generic")+' '+clean(d.model||"Scale")+' · '+clean(d.model_id||"")+'</div>';
   if(!listener)return '<div class="card conn-card">'+title+
     '<p class="muted">Host: <code>127.0.0.1</code> · Read-only MT-SICS-style <code>S</code>/<code>SI</code> subset. Not a vendor USB/serial device.</p>'+
     '<label class="field"><span>TCP port</span><input id="tcp-port-'+clean(d.id)+'" inputmode="numeric" type="number" min="0" max="65535" value="0"></label>'+
     '<p class="small">0 = automatically assigned port. Manual ports must be 1024–65535. The listener starts only after confirmation.</p>'+
     '<div class="row mt">'+button("Start localhost TCP","tcp-start:"+d.id,"primary")+'</div></div>';
   const events=listener.events||[];
   return '<div class="card conn-card">'+title+
     '<p><strong class="conn-endpoint">127.0.0.1:'+clean(listener.port)+'</strong> '+
     badge(listener.clients+" client(s)")+'</p><p class="muted">Commands: '+clean(listener.requests)+' · SICS read-only subset · Live until deactivated</p>'+
     '<div class="conn-controls"><div class="grid two"><label class="field"><span>Gross kg</span><input type="number" step=".001" min="0" id="tcp-gross-'+clean(d.id)+'" value="'+clean(last.gross_kg??1.25)+'"></label>'+
     '<label class="field"><span>Tare kg</span><input type="number" step=".001" min="0" id="tcp-tare-'+clean(d.id)+'" value="'+clean(last.tare_kg??0)+'"></label>'+
     '<label class="field"><span>Output units</span><select id="tcp-unit-'+clean(d.id)+'">'+["kg","lb","g","oz"].map(u=>'<option value="'+u+'" '+(last.unit===u?"selected":"")+'>'+u+'</option>').join("")+'</select></label>'+
     '<label class="field"><span>Stability</span><select id="tcp-stable-'+clean(d.id)+'"><option value="true" '+(last.stable!==false?"selected":"")+'>Stable</option><option value="false" '+(last.stable===false?"selected":"")+'>Unstable</option></select></label></div>'+
     '<div class="row wrap">'+button("Update simulated weight","tcp-weight:"+d.id,"primary")+
     button("Test real TCP roundtrip","tcp-probe:"+d.id)+'</div></div>'+
     '<label class="field mt"><span>Fault injection</span><select id="tcp-fault-'+clean(d.id)+'">'+
     ["none","busy","disconnect"].map(f=>'<option value="'+f+'" '+(listener.fault===f?"selected":"")+'>'+({none:"No fault",busy:"Busy / temporarily unavailable",disconnect:"Disconnect client"}[f])+'</option>').join("")+'</select></label>'+
     '<div class="row wrap">'+button("Apply fault","tcp-fault:"+d.id)+
     button("Stop TCP listener","tcp-stop:"+d.id,"danger")+'</div>'+
     '<details class="conn-events"><summary>Connection activity ('+events.length+' recent events)</summary><div class="conn-event-list">'+
     (events.length?events.slice(0,16).map(e=>'<div><time>'+clean(e.at.slice(11,19))+'</time><b>'+clean(e.operation)+'</b><span>'+clean(e.result)+'</span></div>').join(""):'<p class="small">No commands yet</p>')+'</div></details>'+
     '</div>';
 }).join("");
 const serialAvailable=state.connections?.serial_supported===true;
 const serialScales=state.devices.filter(d=>d.category==="scale"&&d.transport==="serial");
 const serialRunning=state.connections?.serial_listeners||[];
 const serialCards=serialScales.map(d=>{
   const listener=serialRunning.find(x=>x.device_id===d.id),last=d.last_measurement||{};
   const header='<div class="cardhead"><h2>'+clean(d.name)+'</h2>'+badge(listener?.running?"PTY active":"Not active",listener?.running?"green":"amber")+'</div>'+
     '<div class="conn-meta">'+clean(d.brand||"Generic")+' · '+clean(d.model||"Shipping Scale")+'</div>';
   if(!listener) return '<div class="card conn-card">'+header+'<p class="muted">Create a local pseudo-terminal that a separate serial-capable program can open. This is not USB CDC or a physical serial port.</p>'+
    button("Create serial test port","serial-start:"+d.id,"primary",!serialAvailable)+'</div>';
   const logs=listener.events||[];
   return '<div class="card conn-card">'+header+
     '<div class="conn-serial-path"><code>'+clean(listener.path)+'</code></div>'+
     '<p class="small">Use this OS PTY path from a compatible local application. The port lasts until stopped or the Hub exits.</p>'+
     '<div class="grid two"><label class="field"><span>Gross kg</span><input id="serial-gross-'+clean(d.id)+'" type="number" min="0" step=".001" value="'+clean(last.gross_kg??1.25)+'"></label>'+
     '<label class="field"><span>Tare kg</span><input id="serial-tare-'+clean(d.id)+'" type="number" min="0" step=".001" value="'+clean(last.tare_kg??0)+'"></label>'+
     '<label class="field"><span>Output units</span><select id="serial-unit-'+clean(d.id)+'">'+["kg","lb","g","oz"].map(u=>'<option '+(u===last.unit?"selected":"")+'>'+u+'</option>').join("")+'</select></label>'+
     '<label class="field"><span>Stable reading</span><select id="serial-stable-'+clean(d.id)+'"><option value="true" '+(last.stable!==false?"selected":"")+'>Yes</option><option value="false" '+(last.stable===false?"selected":"")+'>No</option></select></label></div>'+
     '<div class="row wrap">'+button("Update serial weight","serial-weight:"+d.id,"primary")+button("Test serial roundtrip","serial-probe:"+d.id)+'</div>'+
     '<label class="field mt"><span>Serial fault</span><select id="serial-fault-'+clean(d.id)+'">'+["none","busy","disconnect"].map(f=>'<option value="'+f+'" '+(listener.fault===f?"selected":"")+'>'+({none:"No fault",busy:"Busy reply",disconnect:"Silence / no reply"}[f])+'</option>').join("")+'</select></label>'+
     '<div class="row wrap">'+button("Apply fault","serial-fault:"+d.id)+button("Close serial port","serial-stop:"+d.id,"danger")+'</div>'+
     '<details class="conn-events"><summary>Serial activity ('+logs.length+' events)</summary><div class="conn-event-list">'+
     logs.slice(0,12).map(e=>'<div><time>'+clean(e.at.slice(11,19))+'</time><b>'+clean(e.operation)+'</b><span>'+clean(e.result)+'</span></div>').join("")+'</div></details>'+
     '</div>';
 }).join("");
 return heading("UNIVERSAL CONNECTION ENGINE","TCP Device Connections",
   "Expose a saved network scale to other applications on this computer. Test actual TCP sockets without real hardware.",
   button("Refresh status","refresh"))+
  '<div class="notice warn"><b>Local-network boundary</b>These endpoints bind to <code>127.0.0.1</code> only. They are accessible by other programs on your own computer; no LAN, BLE, USB or Windows COM device is created. This is a limited MT-SICS-style test protocol, not a certified METTLER TOLEDO implementation.</div>'+
  '<div class="mt">'+overview+'</div>'+
  '<div class="conn-heading"><h2>Network scale fixtures</h2><p class="muted">Only scale profiles configured with Network TCP/IP can start a listener.</p></div>'+
  '<div class="grid two">'+(options||'<div class="card"><h2>No Network scale profiles yet</h2><p class="muted">Create Device → Shipping Scale → Generic Shipping Scale Fixture or METTLER TOLEDO BC reference → Network TCP/IP. Then return here.</p>'+button("Create Scale","wizard","primary")+'</div>')+'</div>'+
  '<div class="conn-heading"><h2>Serial / COM-compatible fixtures</h2><p class="muted">macOS and Linux: real pseudo-terminal paths. Windows virtual COM remains planned and requires a different driver or API.</p></div>'+
  '<div class="grid two">'+(serialCards||'<div class="card"><h2>No Serial scale profile</h2><p class="small">Create Device → Shipping Scale → Generic or METTLER TOLEDO reference → RS-232 / COM. Then activate it here.</p>'+button("Create Scale","wizard","primary")+'</div>')+'</div>'+
  '<div class="card mt"><h2>Serial protocol scope</h2><p class="muted">Send ASCII S or SI followed by CRLF to the PTY path. This is a generic MT-SICS-style subset, not an official brand emulation. In serial mode, Disconnect fault simulates no reply rather than physical USB unplugging.</p></div>'+
  '<div class="card mt"><h2>Client example</h2><p class="muted">Use the port above in a separate application or terminal. Send SI to read a weight; use I0 for the implemented-command inventory, I2 for generic model/capacity, I3 for simulator version, or I4 for a simulated ID. This does not claim full MT-SICS support.</p>'+
  '<pre class="conn-code">python3 -c \'import socket; s=socket.create_connection(("127.0.0.1", PORT)); s.sendall(b"SI\\r\\n"); print(s.recv(128)); s.close()\'</pre>'+
  '<p class="small">Replace PORT with your active port number. No listener auto-starts after restarting Devices Simulator. Stop it using the button above.</p></div>';
}
async function connectionAction(action){
 const split=action.indexOf(":",4);
 const op=action.slice(4,split),id=action.slice(split+1);
 try{
  if(op==="start"){
   const port=Number(E("tcp-port-"+id)?.value||"0");
   if(!Number.isInteger(port)||port<0||port>65535)throw Error("Port must be 0 or 1024–65535");
   if(!confirm("Start a TCP server on 127.0.0.1:"+ (port||"automatic port")+"? Other local processes can connect to this simulated scale."))return;
   const response=await post("/api/connections/start",{device_id:id,port,confirm:true});
   await refresh();showToast("Local TCP scale listening on port "+response.connection.port);return;
  }
  if(op==="stop"){
   if(!confirm("Stop this local TCP listener? Connected applications will lose their scale connection."))return;
   await post("/api/connections/stop",{device_id:id,confirm:true});
   await refresh();showToast("TCP listener stopped");return;
  }
  if(op==="probe"){
   const response=await post("/api/connections/probe",{device_id:id,confirm:true});
   await refresh();showToast(response.probe.passed?"TCP roundtrip OK: "+response.probe.response_ascii.trim():"TCP probe failed",!response.probe.passed);return;
  }
  if(op==="fault"){
   await post("/api/connections/fault",{device_id:id,fault:E("tcp-fault-"+id)?.value,confirm:true});
   await refresh();showToast("Connection fault updated");return;
  }
  if(op==="weight"){
   const reading=await post("/api/devices/"+encodeURIComponent(id)+"/scale-reading",{
    gross_kg:Number(E("tcp-gross-"+id)?.value),
    tare_kg:Number(E("tcp-tare-"+id)?.value),
    unit:E("tcp-unit-"+id)?.value||"kg",
    stable:E("tcp-stable-"+id)?.value==="true"
   });
   await refresh();showToast("Updated TCP scale fixture: "+reading.reading.weight+" "+reading.reading.unit);return;
  }
 }catch(e){showToast(e.message,true)}
}

async function serialAction(action){
 const idx=action.indexOf(":",7),op=action.slice(7,idx),id=action.slice(idx+1);
 try{
  if(op==="start"){
   if(!confirm("Create a local POSIX pseudo-terminal for this simulated scale? Other processes on this computer may open it."))return;
   const result=await post("/api/connections/serial-start",{device_id:id,confirm:true});
   await refresh();showToast("Serial path created: "+result.connection.path);return;
  }
  if(op==="stop"){
   if(!confirm("Close this serial PTY path? Existing clients will lose the endpoint."))return;
   await post("/api/connections/serial-stop",{device_id:id,confirm:true});
   await refresh();showToast("Serial fixture stopped");return;
  }
  if(op==="probe"){
   const result=await post("/api/connections/serial-probe",{device_id:id,confirm:true});
   await refresh();showToast(result.probe.passed?"Serial PTY test OK: "+result.probe.response_ascii.trim():"Serial PTY roundtrip failed",!result.probe.passed);return;
  }
  if(op==="fault"){
   await post("/api/connections/serial-fault",{
    device_id:id,fault:E("serial-fault-"+id)?.value,confirm:true});
   await refresh();showToast("Serial fault updated");return;
  }
  if(op==="weight"){
   const reply=await post("/api/devices/"+encodeURIComponent(id)+"/scale-reading",{
    gross_kg:Number(E("serial-gross-"+id)?.value),
    tare_kg:Number(E("serial-tare-"+id)?.value),
    unit:E("serial-unit-"+id)?.value||"kg",
    stable:E("serial-stable-"+id)?.value==="true"
   });
   await refresh();showToast("Serial scale now reads "+reply.reading.weight+" "+reply.reading.unit);return;
  }
 }catch(e){showToast(e.message,true)}
}
