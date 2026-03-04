"""
ActivityWatch tracker
- Records window activity + AFK state as clean chunks
- Only writes a new chunk when something actually changes

python -m pip install requests (in venv)
"""

import json
import os
import signal
import time
from datetime import datetime, timezone

import requests

# ──────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────
API_BASE  = "http://localhost:5600/api/0"
DATA_DIR  = "./activityTracker"
OUT_FILE  = os.path.join(DATA_DIR, "activity.json")
INTERVAL  = 10   # seconds between polls

# ──────────────────────────────────────────────────────────────────
# Graceful shutdown
# ──────────────────────────────────────────────────────────────────
RUNNING = True

def _stop(*_):
    global RUNNING
    print("\nStopping tracker...")
    RUNNING = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

# ──────────────────────────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────────────────────────
os.makedirs(DATA_DIR, exist_ok=True)


def _get(path: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [warn] GET {path} — {e}")
        return None


def find_bucket(prefix: str) -> str | None:
    buckets = _get("/buckets")
    if not buckets:
        return None
    for bid in buckets:
        if bid.startswith(prefix):
            return bid
    return None


def latest_event(bucket_id: str) -> dict | None:
    events = _get(f"/buckets/{bucket_id}/events", {"limit": 1})
    return events[0] if events else None


# ──────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────

def load_chunks() -> list:
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE) as f:
                return json.load(f).get("chunks", [])
        except Exception:
            pass
    return []


def save_chunks(chunks: list):
    with open(OUT_FILE, "w") as f:
        json.dump({
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "chunks": chunks,
        }, f, indent=2)


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    print("ActivityWatch tracker started. Ctrl-C to stop.")
    print(f"Output → {OUT_FILE}\n")

    win_bucket = find_bucket("aw-watcher-window_")
    afk_bucket = find_bucket("aw-watcher-afk_")

    print(f"Window bucket : {win_bucket or '(not found)'}")
    print(f"AFK bucket    : {afk_bucket or '(not found)'}\n")

    if not win_bucket and not afk_bucket:
        print("[error] No buckets found. Is ActivityWatch running?")
        return

    chunks = load_chunks()

    # State of the currently open (unfinished) chunk
    current = {
        "start":      None,
        "app":        None,
        "title":      None,
        "afk_status": None,   # "afk" | "not-afk" | "unknown"
    }

    def close_chunk(end_ts: str):
        """Finalise the open chunk and append it to the list."""
        if current["start"] is None:
            return
        start_dt = datetime.fromisoformat(current["start"])
        end_dt   = datetime.fromisoformat(end_ts)
        duration = round((end_dt - start_dt).total_seconds(), 1)
        if duration < 1:
            return
        chunks.append({
            "start":            current["start"],
            "end":              end_ts,
            "duration_seconds": duration,
            "app":              current["app"]        or "Unknown",
            "title":            current["title"]      or "",
            "afk_status":       current["afk_status"] or "unknown",
        })

    def open_chunk(ts: str, app: str, title: str, afk: str):
        current["start"]      = ts
        current["app"]        = app
        current["title"]      = title
        current["afk_status"] = afk

    while RUNNING:
        now = datetime.now(timezone.utc).isoformat()

        # ── fetch latest events ────────────────────────────────────
        win_ev = latest_event(win_bucket) if win_bucket else None
        afk_ev = latest_event(afk_bucket) if afk_bucket else None

        app   = (win_ev or {}).get("data", {}).get("app",    "Unknown")
        title = (win_ev or {}).get("data", {}).get("title",  "")
        afk   = (afk_ev or {}).get("data", {}).get("status", "unknown")

        # ── only act when something actually changes ───────────────
        changed = (
            app   != current["app"]        or
            title != current["title"]      or
            afk   != current["afk_status"]
        )

        if changed:
            close_chunk(now)
            save_chunks(chunks)
            open_chunk(now, app, title, afk)
            print(f"[{now}]  afk={afk:9s}  {app} — {title[:70]}")

        time.sleep(INTERVAL)

    # ── flush final open chunk on exit ─────────────────────────────
    close_chunk(datetime.now(timezone.utc).isoformat())
    save_chunks(chunks)
    print(f"\nSaved {len(chunks)} chunks → {OUT_FILE}")


if __name__ == "__main__":
    main()