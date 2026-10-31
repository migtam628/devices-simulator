"""Deliberately constrained, opt-in local print capture retention management.

Only authentic, timestamped job directories under the configured output root
are eligible. Never follow symlinks, scan outside the output root or delete
without an exact recently rechecked preview fingerprint.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .engine import PROFILES

MAX_RETENTION_DAYS = 3650
MAX_CLEANUP_BATCH = 100


def _days(days):
    if type(days) is not int or not 1 <= days <= MAX_RETENTION_DAYS:
        raise ValueError("Retention days must be a whole number between 1 and 3650")
    return days


def _snapshot(root: Path, days: int, now: datetime):
    if not root.is_dir():
        raise ValueError("Capture output folder does not exist")
    cutoff = now - timedelta(days=days)
    found = []
    for profile in root.iterdir():
        if profile.name not in PROFILES or profile.is_symlink() or not profile.is_dir():
            continue
        for folder in profile.iterdir():
            if folder.is_symlink() or not folder.is_dir():
                continue
            meta = folder / "job.json"
            if not meta.is_file() or meta.is_symlink():
                continue
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get("id"), str):
                    continue
                when = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
                if when.tzinfo is None or when > cutoff:
                    continue
                if data.get("profile") != profile.name:
                    continue
                if not folder.resolve().is_relative_to(root):
                    continue
                manifest = []
                safe = True
                for directory, names, files in os.walk(folder, followlinks=False):
                    base = Path(directory)
                    for name in names + files:
                        child = base / name
                        if child.is_symlink():
                            safe = False
                            break
                        if child.is_file():
                            stat = child.stat()
                            manifest.append((str(child.relative_to(folder)), stat.st_size, stat.st_mtime_ns))
                        elif not child.is_dir():
                            safe = False
                            break
                    if not safe:
                        break
                if not safe:
                    continue
                found.append({"path": folder, "job_id": data["id"],
                              "timestamp": when.isoformat(),
                              "bytes": sum(entry[1] for entry in manifest),
                              "manifest": sorted(manifest)})
            except (OSError, ValueError, KeyError, TypeError):
                # Unknown or damaged files are NEVER deleted.
                continue
    found.sort(key=lambda obj: (obj["timestamp"], str(obj["path"])))
    batch = found[:MAX_CLEANUP_BATCH]
    digest = hashlib.sha256()
    for entry in batch:
        details = (str(entry["path"].relative_to(root)), entry["job_id"],
                   entry["timestamp"], entry["manifest"])
        digest.update(repr(details).encode("utf-8"))
        digest.update(b"\n")
    return batch, len(found), digest.hexdigest()


def retention_preview(output: str | Path, days: int, *, now=None) -> dict:
    """Read only: return a conservative deletion plan, never file contents."""
    days = _days(days)
    root = Path(output).expanduser().resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("A timezone-aware reference time is required")
    batch, total, fingerprint = _snapshot(root, days, now)
    return {
        "scope": "local_capture_jobs_only", "days": days,
        "eligible_jobs": total, "batch_jobs": len(batch),
        "batch_bytes": sum(entry["bytes"] for entry in batch),
        "max_batch": MAX_CLEANUP_BATCH, "more_remaining": total > len(batch),
        "fingerprint": fingerprint,
        "note": "Preview only; no files deleted. History references to removed JPGs will remain.",
    }


def retention_cleanup(output: str | Path, days: int, fingerprint: str, *,
                      confirm=False, now=None) -> dict:
    """Remove only exact-preview aged capture jobs after explicit approval."""
    if confirm is not True:
        raise ValueError("Explicit confirmation is required to delete captures")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ValueError("Provide the matching retention preview fingerprint")
    days = _days(days)
    root = Path(output).expanduser().resolve()
    now = now or datetime.now(timezone.utc)
    batch, total, current = _snapshot(root, days, now)
    if fingerprint != current:
        raise RuntimeError("Capture output changed; obtain and review a new cleanup preview")
    if not batch:
        return {"deleted_jobs": 0, "deleted_bytes": 0, "remaining_jobs": 0}
    deleted = 0
    reclaimed = 0
    for entry in batch:
        path = entry["path"]
        # Recheck each directory immediately before deletion. Never traverse
        # symlinks, and refuse any per-job contents changed since preview.
        check, _, _ = _snapshot(root, days, now)
        updated = next((x for x in check if x["path"] == path), None)
        if updated is None or updated["manifest"] != entry["manifest"]:
            raise RuntimeError("Capture output changed during cleanup; stopped safely")
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError("Capture path is not safe to delete")
        shutil.rmtree(path)
        deleted += 1
        reclaimed += entry["bytes"]
    return {"deleted_jobs": deleted, "deleted_bytes": reclaimed,
            "remaining_jobs": max(0, total - deleted)}
