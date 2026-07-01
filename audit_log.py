"""Structured, append-only audit log.

Every attribution decision and (in M5) every appeal is written here as one JSON
object per line (JSON Lines). This keeps the log structured and greppable without a
database, and makes GET /log a simple file read. Extended in M4 (second signal
scores) and M5 (appeal records + status updates).
"""

import json
import os
import threading
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.jsonl")

# Appends must be atomic relative to each other under Flask's threaded server.
_lock = threading.Lock()


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append(entry: dict) -> dict:
    """Append one structured entry, stamping a UTC timestamp if absent."""
    entry.setdefault("timestamp", _utc_now_iso())
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return entry


def read_all() -> list:
    """Return every log entry, oldest first. Empty list if the log doesn't exist."""
    if not os.path.exists(LOG_PATH):
        return []
    entries = []
    with _lock:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def find_decision(content_id: str):
    """Return the most recent 'classified' decision for a content_id, or None.

    Used by the appeal endpoint (M5) to attach an appeal to its original decision.
    """
    match = None
    for entry in read_all():
        if entry.get("content_id") == content_id and entry.get("kind") == "decision":
            match = entry
    return match
