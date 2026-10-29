"""Local-only Advanced Studio graph storage, validation and execution.

The Studio uses in-app fixtures and managed opt-in TCP/POSIX serial reads
through existing local adapters, not arbitrary hosts or device paths.
"""
from __future__ import annotations

import copy
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

NODE_KINDS = ("start", "barcode", "scale", "tcp_scale", "serial_scale", "condition", "capture", "output")
MAX_NODES = 24
MAX_EDGES = 48
EXPORT_FORMAT = "devices-simulator-studio"
EXPORT_VERSION = 1
MAX_IMPORT_BYTES = 64 * 1024
LIVE_TIMEOUT_SECONDS = 15 * 60
LIVE_EFFECT_TYPES = frozenset(("scale", "tcp_scale", "serial_scale", "capture"))
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
LABEL_RE = re.compile(r"^[^\x00-\x1f]{1,80}$")
DEVICE_KINDS = {"scale": {"scale"}, "capture": {"office_printer", "label_printer", "scanner"}}


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_workflow(payload, devices):
    """Normalize an editable DAG. No arbitrary executable code or URLs allowed."""
    if not isinstance(payload, dict):
        raise ValueError("Workflow must be an object")
    title = payload.get("name")
    if not isinstance(title, str) or not LABEL_RE.fullmatch(title.strip()):
        raise ValueError("Workflow name must be 1–80 printable characters")
    raw_nodes, raw_edges = payload.get("nodes"), payload.get("edges")
    if not isinstance(raw_nodes, list) or not 2 <= len(raw_nodes) <= MAX_NODES:
        raise ValueError(f"Workflow requires 2–{MAX_NODES} nodes")
    if not isinstance(raw_edges, list) or len(raw_edges) > MAX_EDGES:
        raise ValueError(f"Workflow supports at most {MAX_EDGES} edges")

    device_map = {d["id"]: d for d in devices}
    nodes, by_id = [], {}
    for original in raw_nodes:
        if not isinstance(original, dict):
            raise ValueError("Invalid workflow node")
        ident, kind = original.get("id"), original.get("type")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident) or ident in by_id:
            raise ValueError("Node IDs must be unique simple identifiers")
        if kind not in NODE_KINDS:
            raise ValueError(f"Unsupported node type: {kind}")
        x, y = original.get("x", 40), original.get("y", 60)
        if type(x) not in (int, float) or type(y) not in (int, float):
            raise ValueError("Node coordinates must be finite numbers")
        if not (0 <= x <= 1800 and 0 <= y <= 1200):
            raise ValueError("Node position outside the canvas")
        config = original.get("config") or {}
        if not isinstance(config, dict):
            raise ValueError("Node settings must be an object")
        normalized = {}
        if kind == "barcode":
            value = config.get("value", "TEST-1001")
            if not isinstance(value, str) or not 1 <= len(value) <= 80 or any(ord(c) < 32 for c in value):
                raise ValueError("Barcode fixture must be 1–80 printable characters")
            normalized = {"value": value}
        elif kind == "scale":
            ident_dev = config.get("device_id")
            device = device_map.get(ident_dev)
            if not device or device.get("category") != "scale":
                raise ValueError("Scale node must reference an existing scale fixture")
            gross, tare = config.get("gross_kg", 1.25), config.get("tare_kg", 0)
            if type(gross) not in (int, float) or type(tare) not in (int, float):
                raise ValueError("Scale fixture values must be numbers")
            if not (0 <= gross <= 10000 and 0 <= tare <= gross):
                raise ValueError("Invalid scale gross/tare values")
            unit = config.get("unit", "kg")
            if unit not in ("kg", "lb", "g", "oz"):
                raise ValueError("Unsupported scale units")
            stable = config.get("stable", True)
            if type(stable) is not bool:
                raise ValueError("Scale stability must be boolean")
            normalized = {"device_id": ident_dev, "gross_kg": gross, "tare_kg": tare,
                          "unit": unit, "stable": stable}
        elif kind == "tcp_scale":
            ident_dev = config.get("device_id")
            device = device_map.get(ident_dev)
            if not device or device.get("category") != "scale" or device.get("transport") != "network":
                raise ValueError("TCP scale node requires an existing scale with Network transport")
            normalized = {"device_id": ident_dev}
        elif kind == "serial_scale":
            ident_dev = config.get("device_id")
            device = device_map.get(ident_dev)
            if not device or device.get("category") != "scale" or device.get("transport") != "serial":
                raise ValueError("Serial scale node requires an existing scale with RS-232 / serial transport")
            normalized = {"device_id": ident_dev}
        elif kind == "condition":
            field = config.get("field", "weight")
            operator = config.get("operator", "gte")
            value = config.get("value", 1.0)
            if field == "weight":
                if operator not in ("gte", "lt") or type(value) not in (int, float):
                    raise ValueError("Weight condition needs a numeric >= or < comparison")
                if not 0 <= value <= 10000:
                    raise ValueError("Weight condition threshold must be 0–10000")
            elif field == "barcode":
                if operator not in ("equals", "contains") or not isinstance(value, str):
                    raise ValueError("Barcode condition needs a text equals/contains comparison")
                if not 1 <= len(value) <= 80 or any(ord(c) < 32 for c in value):
                    raise ValueError("Barcode condition value must be printable (1–80 chars)")
            else:
                raise ValueError("Condition field must be weight or barcode")
            normalized = {"field": field, "operator": operator, "value": value}
        elif kind == "capture":
            ident_dev = config.get("device_id")
            device = device_map.get(ident_dev)
            if not device or device.get("category") not in DEVICE_KINDS["capture"]:
                raise ValueError("Capture node must reference an existing printer or scan fixture")
            title_override = config.get("title", "Studio Capture")
            if not isinstance(title_override, str) or not LABEL_RE.fullmatch(title_override):
                raise ValueError("Capture title must be 1–80 printable characters")
            normalized = {"device_id": ident_dev, "title": title_override}
        node = {"id": ident, "type": kind, "x": int(x), "y": int(y), "config": normalized}
        nodes.append(node)
        by_id[ident] = node

    if sum(n["type"] == "start" for n in nodes) != 1:
        raise ValueError("Workflow requires exactly one Start node")
    if not any(n["type"] == "output" for n in nodes):
        raise ValueError("Workflow requires an Output node")
    edges, indegree, outgoing = [], {nid: 0 for nid in by_id}, {nid: [] for nid in by_id}
    used = set()
    for edge in raw_edges:
        if not isinstance(edge, dict):
            raise ValueError("Invalid workflow edge")
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id or source == target:
            raise ValueError("Connections must link different existing nodes")
        if (source, target) in used:
            raise ValueError("Duplicate connection")
        if by_id[target]["type"] == "start" or by_id[source]["type"] == "output":
            raise ValueError("Start cannot receive, and Output cannot send, connections")
        if by_id[source]["type"] == "condition":
            if edge.get("branch") not in ("true", "false"):
                raise ValueError("Condition edges must specify branch true or false")
            branch = edge["branch"]
        else:
            if "branch" in edge:
                raise ValueError("Only Condition edges may specify a branch")
            branch = None
        used.add((source, target))
        edges.append({"source": source, "target": target, **({"branch": branch} if branch else {})})
        outgoing[source].append(target)
        indegree[target] += 1

    # Deterministic topological walk; reject cycles and unconnected islands.
    queue = sorted(nid for nid, degree in indegree.items() if degree == 0)
    order = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for target in outgoing[nid]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
                queue.sort()
    if len(order) != len(nodes):
        raise ValueError("Workflow cannot contain cycles")
    for node in nodes:
        if node["type"] == "condition":
            branches = [e["branch"] for e in edges if e["source"] == node["id"]]
            if sorted(branches) != ["false", "true"]:
                raise ValueError("Each Condition node requires exactly one true and one false edge")
    start_id = next(n["id"] for n in nodes if n["type"] == "start")
    reachable = {start_id}
    for nid in order:
        if nid in reachable:
            reachable.update(outgoing[nid])
    if len(reachable) != len(nodes):
        raise ValueError("Connect every node to the Start path")
    if not any(n["type"] == "output" and n["id"] in reachable for n in nodes):
        raise ValueError("Workflow needs a connected Output node")

    return {"name": title.strip(), "nodes": nodes, "edges": edges, "order": order}


class StudioManager:
    def __init__(self, state_dir: Path, hub_store, connections=None):
        self.connections = connections
        self.path = Path(state_dir) / "studio_workflows.json"
        self.hub = hub_store
        self.lock = threading.RLock()
        self._live = None  # one volatile debug session per Hub; never persisted
        if not self.path.exists():
            self._write({"version": 1, "workflows": [], "runs": []})

    def _read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data):
        tmp = self.path.with_name("." + self.path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def snapshot(self):
        with self.lock:
            data = self._read()
            return copy.deepcopy(data)


    def inspect(self, payload, checkpoints=None):
        """Validate an unsaved graph and return a READ-ONLY execution walkthrough.

        No work orders, capture jobs, scale measurements, connections, state
        writes, or historical run records are created. Checkpoints are only
        inspection markers, not runtime breakpoints.
        """
        graph = validate_workflow(payload, self.hub.list_devices())
        if checkpoints is None:
            checkpoints = []
        if not isinstance(checkpoints, list) or len(checkpoints) > MAX_NODES:
            raise ValueError("Checkpoints must be a bounded list of node IDs")
        if any(not isinstance(nid, str) or not ID_RE.fullmatch(nid) for nid in checkpoints):
            raise ValueError("Invalid checkpoint ID")
        node_map = {n["id"]: n for n in graph["nodes"]}
        if len(set(checkpoints)) != len(checkpoints) or any(nid not in node_map for nid in checkpoints):
            raise ValueError("Checkpoints must reference distinct existing nodes")
        incoming = {nid: [] for nid in node_map}
        outgoing = {nid: [] for nid in node_map}
        for edge in graph["edges"]:
            incoming[edge["target"]].append(edge)
            outgoing[edge["source"]].append(edge)
        actions = {
            "start": ("local trigger", False, False),
            "barcode": ("barcode fixture", False, False),
            "scale": ("simulated scale reading (updates local measurement)", True, False),
            "tcp_scale": ("read already-active localhost TCP scale", True, True),
            "serial_scale": ("read already-active local POSIX serial scale", True, True),
            "condition": ("evaluate weight or barcode; branch determined at runtime", False, False),
            "capture": ("generate a new local JPG capture", True, False),
            "output": ("inspect accumulated run output", False, False),
        }
        plan = []
        for index, nid in enumerate(graph["order"]):
            node = node_map[nid]
            label, side_effect, adapter_required = actions[node["type"]]
            item = {
                "step": index + 1,
                "node_id": nid,
                "type": node["type"],
                "action": label,
                "may_mutate_local_state": side_effect,
                "requires_active_adapter": adapter_required,
                "checkpoint": nid in checkpoints,
                "incoming": copy.deepcopy(incoming[nid]),
                "outgoing": copy.deepcopy(outgoing[nid]),
            }
            if node["type"] == "condition":
                item["condition"] = copy.deepcopy(node["config"])
                item["note"] = "TRUE/FALSE selection is unknown until a real execution"
            if node["type"] in ("scale", "tcp_scale", "serial_scale", "capture"):
                item["device_id"] = node["config"]["device_id"]
            plan.append(item)
        return {
            "mode": "read_only_preflight",
            "execution_performed": False,
            "name": graph["name"],
            "node_count": len(plan),
            "edge_count": len(graph["edges"]),
            "steps": plan,
            "checkpoints": checkpoints[:],
            "may_generate_jpgs_on_execution": any(n["type"] == "capture" for n in graph["nodes"]),
            "may_read_managed_adapters_on_execution": any(n["type"] in ("tcp_scale", "serial_scale") for n in graph["nodes"]),
            "note": "Read-only walkthrough. Checkpoints are inspection markers, not live execution pauses.",
        }

    def save(self, payload):
        graph = validate_workflow(payload, self.hub.list_devices())
        with self.lock:
            data = self._read()
            ident = payload.get("id")
            if ident is not None and (not isinstance(ident, str) or not ID_RE.fullmatch(ident)):
                raise ValueError("Invalid workflow identifier")
            existing = next((w for w in data["workflows"] if w["id"] == ident), None)
            if ident and existing is None:
                raise LookupError("Workflow does not exist")
            if existing:
                if payload.get("revision") != existing["revision"]:
                    raise RuntimeError("Workflow changed since you opened it; reload before saving")
                existing.update(graph)
                existing["revision"] += 1
                existing["updated_at"] = now()
                saved = existing
            else:
                if len(data["workflows"]) >= 40:
                    raise ValueError("Maximum 40 saved workflows")
                saved = {"id": uuid.uuid4().hex, "revision": 1, "created_at": now(),
                         "updated_at": now(), **graph}
                data["workflows"].append(saved)
            self._write(data)
            return copy.deepcopy(saved)


    def export_workflow(self, workflow_id):
        """Portable graph only: exclude local persistence metadata, runs and outputs."""
        with self.lock:
            workflow = next((w for w in self._read()["workflows"] if w["id"] == workflow_id), None)
            if not workflow:
                raise LookupError("Workflow not found")
            return {"format": EXPORT_FORMAT, "version": EXPORT_VERSION,
                    "workflow": {"name": workflow["name"],
                                 "nodes": copy.deepcopy(workflow["nodes"]),
                                 "edges": copy.deepcopy(workflow["edges"])}}

    def import_workflow(self, document, device_map=None):
        """Revalidate all nodes/transports and create a NEW saved workflow."""
        if not isinstance(document, dict):
            raise ValueError("Import must be a JSON object")
        try:
            encoded = json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Import must contain valid JSON data") from exc
        if len(encoded) > MAX_IMPORT_BYTES:
            raise ValueError("Import exceeds 64 KB limit")
        if document.get("format") != EXPORT_FORMAT or type(document.get("version")) is not int or document["version"] != EXPORT_VERSION:
            raise ValueError("Unsupported Studio import format or version")
        if not isinstance(document.get("workflow"), dict):
            raise ValueError("Import is missing a workflow graph")
        mapping = {} if device_map is None else device_map
        if not isinstance(mapping, dict) or len(mapping) > MAX_NODES:
            raise ValueError("Device mapping must be a bounded object")
        if any(not isinstance(k, str) or not isinstance(v, str)
               or len(k) > 80 or len(v) > 80 for k, v in mapping.items()):
            raise ValueError("Invalid device mapping identifiers")
        graph = copy.deepcopy(document["workflow"])
        if not isinstance(graph.get("nodes"), list):
            raise ValueError("Import requires a node list")
        for node in graph["nodes"]:
            if not isinstance(node, dict):
                raise ValueError("Invalid imported node")
            cfg = node.get("config")
            if isinstance(cfg, dict) and "device_id" in cfg:
                ident = cfg["device_id"]
                if not isinstance(ident, str):
                    raise ValueError("Invalid imported device identifier")
                cfg["device_id"] = mapping.get(ident, ident)
        normalized = validate_workflow(graph, self.hub.list_devices())
        return self.save({"name": normalized["name"], "nodes": normalized["nodes"],
                          "edges": normalized["edges"]})

    def delete(self, workflow_id):
        with self.lock:
            data = self._read()
            original = len(data["workflows"])
            data["workflows"] = [w for w in data["workflows"] if w["id"] != workflow_id]
            if len(data["workflows"]) == original:
                raise LookupError("Workflow not found")
            self._write(data)
            return True

    def _iter_execution(self, graph):
        """Yield exactly one executed, skipped, or inactive node per next().
        
        Shared by normal runs and manually gated debugging sessions. A suspended
        generator cannot progress unless its caller explicitly advances it.
        """
        trace = []
        nodes = {n["id"]: n for n in graph["nodes"]}
        incoming = {nid: [] for nid in nodes}
        for edge in graph["edges"]:
            incoming[edge["target"]].append(edge)
        results = {}
        for nid in graph["order"]:
            node = nodes[nid]
            prev = []
            blocked = False
            for edge in incoming[nid]:
                parent = results[edge["source"]]
                if parent["status"] in ("failed", "skipped"):
                    blocked = True
                elif parent["status"] == "completed":
                    branch = edge.get("branch")
                    if branch is None or parent.get("decision") == (branch == "true"):
                        prev.append(parent)
            if blocked:
                results[nid] = {"status": "skipped"}
                trace.append({"node_id": nid, "type": node["type"], "status": "skipped",
                              "detail": "Upstream step did not complete"})
                yield copy.deepcopy(trace[-1])
                continue
            if incoming[nid] and not prev:
                results[nid] = {"status": "inactive"}
                trace.append({"node_id": nid, "type": node["type"], "status": "inactive",
                              "detail": "Condition branch was not selected"})
                yield copy.deepcopy(trace[-1])
                continue
            payload = {"barcode": None, "weight": None, "captures": []}
            for item in prev:
                previous = item.get("data", {})
                if previous.get("barcode") is not None:
                    payload["barcode"] = previous["barcode"]
                if previous.get("weight") is not None:
                    payload["weight"] = previous["weight"]
                payload["captures"].extend(previous.get("captures", []))
            kind, cfg = node["type"], node["config"]
            try:
                detail = ""
                if kind == "start":
                    detail = "Local sample event started"
                elif kind == "barcode":
                    payload["barcode"] = cfg["value"]
                    detail = "Barcode fixture supplied test data (no keyboard event)"
                elif kind == "scale":
                    reading = self.hub.simulate_scale_reading(cfg["device_id"], cfg)
                    payload["weight"] = {"value": reading["weight"], "unit": reading["unit"],
                                         "status": reading["status"]}
                    if reading["status"] != "stable":
                        raise ValueError("Scale reading is " + reading["status"])
                    detail = f"Local scale fixture: {reading['weight']} {reading['unit']}"
                elif kind == "tcp_scale":
                    if self.connections is None:
                        raise RuntimeError("Connection Engine not available")
                    reading = self.connections.read_scale(cfg["device_id"])
                    payload["weight"] = {"value": reading["value"], "unit": reading["unit"],
                                         "status": reading["status"]}
                    detail = f"TCP scale read over localhost:{reading['port']}: {reading['raw_response']}"
                elif kind == "serial_scale":
                    if self.connections is None:
                        raise RuntimeError("Connection Engine not available")
                    reading = self.connections.read_serial_scale(cfg["device_id"])
                    payload["weight"] = {"value": reading["value"], "unit": reading["unit"],
                                         "status": reading["status"]}
                    detail = f"Serial scale read over local PTY {reading['path']}: {reading['raw_response']}"
                elif kind == "condition":
                    if cfg["field"] == "weight":
                        reading = payload["weight"]
                        if reading is None or reading.get("status") != "stable":
                            raise ValueError("Weight condition requires an upstream stable scale reading")
                        actual = reading["value"]
                        decision = actual >= cfg["value"] if cfg["operator"] == "gte" else actual < cfg["value"]
                        detail = f"Weight {actual} {reading['unit']} {cfg['operator']} {cfg['value']} = {decision}"
                    else:
                        actual = payload["barcode"]
                        if actual is None:
                            raise ValueError("Barcode condition requires an upstream barcode")
                        decision = (actual == cfg["value"] if cfg["operator"] == "equals"
                                    else cfg["value"] in actual)
                        detail = f"Barcode condition {cfg['operator']} {cfg['value']!r} = {decision}"
                elif kind == "capture":
                    job = self.hub.test_device(cfg["device_id"], title=cfg["title"])
                    if job["status"] != "rendered":
                        raise ValueError(job.get("error", "Document capture failed"))
                    payload["captures"].append({"job_id": job["id"],
                                                "images": job.get("images", []),
                                                "profile": job["profile"]})
                    detail = f"{len(job.get('images', []))} JPG page(s) captured locally"
                elif kind == "output":
                    detail = f"{len(payload['captures'])} capture job(s) in run"
                results[nid] = {"status": "completed", "data": payload}
                if kind == "condition":
                    results[nid]["decision"] = decision
                completed = {"node_id": nid, "type": kind, "status": "completed",
                             "detail": detail}
                if kind == "condition":
                    completed["decision"] = decision
                    completed["selected_branch"] = "true" if decision else "false"
                if kind == "capture":
                    completed["job_id"] = job["id"]
                    completed["images"] = job.get("images", [])
                if kind in ("scale", "tcp_scale", "serial_scale"):
                    completed["weight"] = payload["weight"]
                trace.append(completed)
            except (ValueError, LookupError, RuntimeError, OSError) as exc:
                results[nid] = {"status": "failed"}
                trace.append({"node_id": nid, "type": kind, "status": "failed",
                              "detail": str(exc)[:200]})
            yield copy.deepcopy(trace[-1])
        status = "completed" if all(t["status"] in ("completed", "inactive") for t in trace) else "failed"
        return trace, status

    def _live_current(self):
        session = self._live
        if session and time.monotonic() - session["last_used"] > LIVE_TIMEOUT_SECONDS:
            # Do not silently replay pending captures after TTL expiry.
            self._live = None
            return None
        return session

    def _live_view(self, session):
        order = session["graph"]["order"]
        idx = session["index"]
        node = None
        if idx < len(order):
            current = next(n for n in session["graph"]["nodes"] if n["id"] == order[idx])
            node = {"id": current["id"], "type": current["type"],
                    "requires_confirmation": current["type"] in LIVE_EFFECT_TYPES}
        return {"session_id": session["id"], "workflow_id": session["workflow_id"],
                "workflow_revision": session["revision"], "status": "paused",
                "expected_step": idx, "total_steps": len(order),
                "next_node": node, "steps": copy.deepcopy(session["trace"]),
                "expires_in_seconds": max(0, int(LIVE_TIMEOUT_SECONDS -
                    (time.monotonic() - session["last_used"]))),
                "note": "One step per authenticated request; pending steps never execute automatically."}

    def live_status(self):
        with self.lock:
            session = self._live_current()
            return copy.deepcopy(self._live_view(session)) if session else None

    def live_start(self, workflow_id, revision):
        """Create one volatile paused session from an EXACT saved workflow revision."""
        if not isinstance(workflow_id, str) or not ID_RE.fullmatch(workflow_id):
            raise ValueError("Invalid saved workflow identifier")
        if type(revision) is not int or revision < 1:
            raise ValueError("Live debugging requires the saved workflow revision")
        with self.lock:
            if self._live_current() is not None:
                raise RuntimeError("A debug session is already active; inspect or cancel it first")
            saved = next((w for w in self._read()["workflows"] if w["id"] == workflow_id), None)
            if saved is None:
                raise LookupError("Saved workflow not found")
            if saved["revision"] != revision:
                raise RuntimeError("Workflow revision changed; reload and save before debugging")
            graph = validate_workflow(saved, self.hub.list_devices())
            self._live = {"id": uuid.uuid4().hex, "workflow_id": workflow_id,
                          "revision": saved["revision"], "snapshot": {
                              "name": saved["name"], "nodes": copy.deepcopy(saved["nodes"]),
                              "edges": copy.deepcopy(saved["edges"])},
                          "graph": graph, "cursor": self._iter_execution(graph),
                          "index": 0, "trace": [], "started_at": now(),
                          "last_used": time.monotonic()}
            return self._live_view(self._live)

    def _live_record(self, session, status, steps):
        record = {
            "id": uuid.uuid4().hex, "workflow_id": session["workflow_id"],
            "name": session["snapshot"]["name"], "status": status,
            "started_at": session["started_at"], "finished_at": now(),
            "steps": copy.deepcopy(steps), "workflow_snapshot": copy.deepcopy(session["snapshot"]),
            "workflow_revision": session["revision"], "replayed_from": None,
            "mode": "confirmed_manual_step_debugger",
        }
        data = self._read()
        data["runs"].insert(0, record)
        data["runs"] = data["runs"][:80]
        self._write(data)
        return record

    def live_step(self, session_id, expected_step, confirm=False):
        """Advance exactly one node, and never duplicate it when a request is retried."""
        if not isinstance(session_id, str) or not ID_RE.fullmatch(session_id):
            raise ValueError("Invalid debug session identifier")
        if type(expected_step) is not int or expected_step < 0:
            raise ValueError("An exact nonnegative expected step is required")
        with self.lock:
            session = self._live_current()
            if not session or session["id"] != session_id:
                raise LookupError("Debug session is missing or expired")
            if session["index"] != expected_step:
                raise RuntimeError("Step has already advanced; reload session status")
            next_id = session["graph"]["order"][session["index"]]
            node = next(n for n in session["graph"]["nodes"] if n["id"] == next_id)
            if node["type"] in LIVE_EFFECT_TYPES and confirm is not True:
                raise ValueError("This step may access a scale or create JPG files; confirm explicitly")
            # Generator is serialized under the same lock as normal runs.
            item = next(session["cursor"])
            session["trace"].append(item)
            session["index"] += 1
            session["last_used"] = time.monotonic()
            if session["index"] == len(session["graph"]["order"]):
                try:
                    next(session["cursor"])
                except StopIteration as done:
                    full_trace, status = done.value
                else:
                    raise RuntimeError("Unexpected extra execution step")
                record = self._live_record(session, status, full_trace)
                self._live = None
                return {"status": status, "finished": True, "run": record,
                        "executed": item, "session": None}
            return {"status": "paused", "finished": False, "executed": item,
                    "session": self._live_view(session)}

    def live_cancel(self, session_id):
        if not isinstance(session_id, str) or not ID_RE.fullmatch(session_id):
            raise ValueError("Invalid debug session identifier")
        with self.lock:
            session = self._live_current()
            if not session or session["id"] != session_id:
                raise LookupError("Debug session is missing or expired")
            record = self._live_record(session, "cancelled", session["trace"])
            self._live = None
            return record

    def run(self, workflow_id, replay_run_id=None):
        """Execute current or historically snapshotted graph using FRESH fixtures."""
        with self.lock:
            data = self._read()
            workflow = next((w for w in data["workflows"] if w["id"] == workflow_id), None)
            if not workflow:
                raise LookupError("Workflow not found")
            source = None
            if replay_run_id is not None:
                if not isinstance(replay_run_id, str) or not ID_RE.fullmatch(replay_run_id):
                    raise ValueError("Invalid replay run identifier")
                source = next((r for r in data["runs"] if r["id"] == replay_run_id
                               and r["workflow_id"] == workflow_id), None)
                if source is None:
                    raise LookupError("Run not found for this workflow")
                if not isinstance(source.get("workflow_snapshot"), dict):
                    raise ValueError("This older run has no snapshot and cannot be replayed")
            execution = source["workflow_snapshot"] if source else workflow
            executed_revision = source.get("workflow_revision") if source else workflow["revision"]
            run_id = uuid.uuid4().hex
            started = now()
            trace = []
            try:
                graph = validate_workflow(execution, self.hub.list_devices())
                cursor = self._iter_execution(graph)
                while True:
                    try:
                        next(cursor)
                    except StopIteration as done:
                        trace, status = done.value
                        break
            except ValueError as exc:
                status = "failed"
                trace = [{"node_id": "validation", "type": "validation", "status": "failed",
                          "detail": str(exc)[:200]}]
            # Retain source graph, not output artifacts or prior results.
            graph_snapshot = {"name": execution["name"],
                              "nodes": copy.deepcopy(execution["nodes"]),
                              "edges": copy.deepcopy(execution["edges"])}
            # Keep history bounded even for repeated workflow runs.
            record = {"id": run_id, "workflow_id": workflow_id, "name": execution["name"],
                      "status": status, "started_at": started, "finished_at": now(), "steps": trace,
                      "workflow_snapshot": graph_snapshot, "workflow_revision": executed_revision,
                      "replayed_from": replay_run_id,
                      "mode": ("local_fixture_and_managed_tcp_serial" if {"tcp_scale", "serial_scale"} <= {n["type"] for n in execution["nodes"]}
                               else "local_fixture_and_managed_tcp" if any(n["type"] == "tcp_scale" for n in execution["nodes"])
                               else "local_fixture_and_managed_posix_serial" if any(n["type"] == "serial_scale" for n in execution["nodes"])
                               else "local_fixture_only")}
            data["runs"].insert(0, record)
            data["runs"] = data["runs"][:80]
            self._write(data)
            return copy.deepcopy(record)
