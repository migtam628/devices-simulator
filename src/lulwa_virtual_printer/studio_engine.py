"""Local-only Advanced Studio graph storage, validation and execution.

The Studio never calls OS printer queues, USB/BLE APIs, barcode keyboard output,
network services, or third-party applications. It operates on existing in-app
device fixtures; a capture job writes an actual local JPG through HubStore.
"""
from __future__ import annotations

import copy
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

NODE_KINDS = ("start", "barcode", "scale", "capture", "output")
MAX_NODES = 24
MAX_EDGES = 48
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
        used.add((source, target))
        edges.append({"source": source, "target": target})
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
    def __init__(self, state_dir: Path, hub_store):
        self.path = Path(state_dir) / "studio_workflows.json"
        self.hub = hub_store
        self.lock = threading.RLock()
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

    def delete(self, workflow_id):
        with self.lock:
            data = self._read()
            original = len(data["workflows"])
            data["workflows"] = [w for w in data["workflows"] if w["id"] != workflow_id]
            if len(data["workflows"]) == original:
                raise LookupError("Workflow not found")
            self._write(data)
            return True

    def run(self, workflow_id):
        """Execute only local fixtures, in graph order. Never perform OS I/O."""
        with self.lock:
            data = self._read()
            workflow = next((w for w in data["workflows"] if w["id"] == workflow_id), None)
            if not workflow:
                raise LookupError("Workflow not found")
            run_id = uuid.uuid4().hex
            started = now()
            trace = []
            try:
                graph = validate_workflow(workflow, self.hub.list_devices())
                nodes = {n["id"]: n for n in graph["nodes"]}
                parents = {nid: [] for nid in nodes}
                for edge in graph["edges"]:
                    parents[edge["target"]].append(edge["source"])
                results = {}
                for nid in graph["order"]:
                    node = nodes[nid]
                    prev = [results[parent] for parent in parents[nid]]
                    if any(r["status"] != "completed" for r in prev):
                        results[nid] = {"status": "skipped"}
                        trace.append({"node_id": nid, "type": node["type"], "status": "skipped",
                                      "detail": "Upstream step did not complete"})
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
                        completed = {"node_id": nid, "type": kind, "status": "completed",
                                     "detail": detail}
                        if kind == "capture":
                            completed["job_id"] = job["id"]
                            completed["images"] = job.get("images", [])
                        if kind == "scale":
                            completed["weight"] = payload["weight"]
                        trace.append(completed)
                    except (ValueError, LookupError, RuntimeError, OSError) as exc:
                        results[nid] = {"status": "failed"}
                        trace.append({"node_id": nid, "type": kind, "status": "failed",
                                      "detail": str(exc)[:200]})
                status = "completed" if all(t["status"] == "completed" for t in trace) else "failed"
            except ValueError as exc:
                status = "failed"
                trace = [{"node_id": "validation", "type": "validation", "status": "failed",
                          "detail": str(exc)[:200]}]
            # Keep history bounded even for repeated workflow runs.
            record = {"id": run_id, "workflow_id": workflow_id, "name": workflow["name"],
                      "status": status, "started_at": started, "finished_at": now(), "steps": trace,
                      "mode": "local_fixture_only"}
            data["runs"].insert(0, record)
            data["runs"] = data["runs"][:80]
            self._write(data)
            return copy.deepcopy(record)
