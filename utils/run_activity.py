"""
ActivityWatch tracker
- Records window activity + AFK state as clean chunks
- Only writes a new chunk when something actually changes
- Only captures events from the moment the script starts
- Clears the output file on each run

python -m pip install requests (in venv)
"""

import json
import os
import signal
import sys
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


def latest_event(bucket_id: str, start: str) -> dict | None:
    """Fetch the most recent event that occurred after `start` (ISO timestamp)."""
    events = _get(f"/buckets/{bucket_id}/events", {"limit": 1, "start": start})
    return events[0] if events else None


# ──────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────

def clear_and_init():
    """Wipe the output file and start fresh."""
    with open(OUT_FILE, "w") as f:
        json.dump({
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "chunks": [],
        }, f, indent=2)
    print(f"Cleared {OUT_FILE}")


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
    # Record exactly when this session started
    session_start = datetime.now(timezone.utc).isoformat()

    print("ActivityWatch tracker started. Ctrl-C to stop.")
    print(f"Session start : {session_start}")
    print(f"Output        → {OUT_FILE}\n")

    # Clear any data from previous runs
    clear_and_init()

    # ── Wait for AW server to be reachable ────────────────────────
    print("Waiting for ActivityWatch server to be reachable...")
    server_max_wait = 120   # seconds – packaged apps take longer to boot AW
    server_waited  = 0
    while server_waited < server_max_wait:
        buckets = _get("/buckets")
        if buckets is not None:
            print(f"  AW server reachable after {server_waited}s")
            break
        time.sleep(2)
        server_waited += 2
        if not RUNNING:
            return
    else:
        print("[error] AW server never became reachable. Exiting.")
        sys.exit(1)

    # ── Wait for watchers to register their buckets ───────────────
    # In a packaged DMG the watchers can take 30-90 s to start and
    # register buckets with the server, so we wait generously.
    print("Waiting for window/AFK watchers to register buckets...")
    watcher_max_wait = 180   # seconds
    watcher_waited   = 0
    win_bucket = None
    afk_bucket = None

    while watcher_waited < watcher_max_wait:
        win_bucket = find_bucket("aw-watcher-window_")
        afk_bucket = find_bucket("aw-watcher-afk_")
        if win_bucket or afk_bucket:
            print(f"  Watcher bucket(s) found after {watcher_waited}s")
            break
        time.sleep(3)
        watcher_waited += 3
        if not RUNNING:
            return
        if watcher_waited % 30 == 0:
            print(f"  Still waiting for buckets... ({watcher_waited}s elapsed)")

    print(f"Window bucket : {win_bucket or '(not found)'}")
    print(f"AFK bucket    : {afk_bucket or '(not found)'}\n")

    if not win_bucket and not afk_bucket:
        print("[warn] No watcher buckets found after waiting. Will still poll and write 'Unknown' entries.")
        # Don't exit – keep running so collate_data has *something* to read

    chunks = []

    # State of the currently open (unfinished) chunk
    current = {
        "start":      None,
        "app":        None,
        "title":      None,
        "afk_status": None,
    }

    def close_chunk(end_ts: str):
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

        # Re-discover buckets if they appeared late
        if not win_bucket:
            win_bucket = find_bucket("aw-watcher-window_")
        if not afk_bucket:
            afk_bucket = find_bucket("aw-watcher-afk_")

        # Only fetch events that happened after this script started
        win_ev = latest_event(win_bucket, session_start) if win_bucket else None
        afk_ev = latest_event(afk_bucket, session_start) if afk_bucket else None

        app   = (win_ev or {}).get("data", {}).get("app",    "Unknown")
        title = (win_ev or {}).get("data", {}).get("title",  "")
        afk   = (afk_ev or {}).get("data", {}).get("status", "unknown")

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