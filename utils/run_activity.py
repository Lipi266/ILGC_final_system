"""
ActivityWatch tracker
- Records window activity + AFK state as clean chunks
- Only writes a new chunk when something actually changes
- Only captures events from the moment the script starts
- Preserves existing data across restarts; appends new session chunks
- Timestamps in IST (UTC+5:30)

python -m pip install requests (in venv)
"""

import json
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

# ──────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────
API_BASE  = "http://localhost:5600/api/0"
DATA_DIR  = "./activityTracker"
OUT_FILE  = os.path.join(DATA_DIR, "activity.json")
INTERVAL  = 10   # seconds between polls

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> str:
    """Return current time as IST ISO-8601 string."""
    return datetime.now(IST).isoformat()


def utc_to_ist(utc_iso: str) -> str:
    """Convert a UTC ISO string (from AW API) to IST ISO string."""
    try:
        # AW timestamps end in +00:00 or Z
        ts = utc_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.astimezone(IST).isoformat()
    except Exception:
        return utc_iso

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
    """
    Fetch the most recent event that occurred after `start`.
    `start` must be a UTC ISO string (as returned by AW API).
    """
    # Convert IST session_start back to UTC for AW query params
    try:
        dt_ist = datetime.fromisoformat(start)
        dt_utc = dt_ist.astimezone(timezone.utc).isoformat()
    except Exception:
        dt_utc = start

    events = _get(f"/buckets/{bucket_id}/events", {"limit": 1, "start": dt_utc})
    return events[0] if events else None


# ──────────────────────────────────────────────────────────────────
# Persistence — append-only; never wipes existing data
# ──────────────────────────────────────────────────────────────────

def load_existing_chunks() -> list:
    """Load chunks from a previous session if the file exists."""
    if not os.path.exists(OUT_FILE):
        return []
    try:
        with open(OUT_FILE, "r") as f:
            data = json.load(f)
        return data.get("chunks", [])
    except Exception:
        return []


def save_chunks(chunks: list):
    with open(OUT_FILE, "w") as f:
        json.dump({
            "last_updated": now_ist(),
            "chunks": chunks,
        }, f, indent=2)


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    # Record exactly when this session started (IST)
    session_start_ist = now_ist()

    print("ActivityWatch tracker started. Ctrl-C to stop.")
    print(f"Session start (IST): {session_start_ist}")
    print(f"Output              → {OUT_FILE}\n")

    # Load any previously saved chunks (don't wipe them)
    chunks = load_existing_chunks()
    print(f"Loaded {len(chunks)} existing chunks from previous session(s).")

    # ── Wait for AW server to be reachable ────────────────────────
    print("Waiting for ActivityWatch server to be reachable...")
    server_max_wait = 120
    server_waited   = 0
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
    # aw-qt manages the watchers; they can take 30-90 s after launch.
    print("Waiting for window/AFK watchers to register buckets...")
    watcher_max_wait = 180
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
        print("[warn] No watcher buckets found. Likely causes:")
        print("  • aw-watcher-window/afk need Accessibility + Screen Recording permissions")
        print("  • System Settings > Privacy & Security > Accessibility — add ActivityWatch")
        print("  • System Settings > Privacy & Security > Screen Recording — add ActivityWatch")
        print("  Continuing — data will show 'Unknown' until permissions are granted.")

    # State of the currently open (unfinished) chunk
    current = {
        "start":      None,
        "app":        None,
        "title":      None,
        "afk_status": None,
    }

    def close_chunk(end_ts_ist: str):
        if current["start"] is None:
            return
        start_dt = datetime.fromisoformat(current["start"])
        end_dt   = datetime.fromisoformat(end_ts_ist)
        duration = round((end_dt - start_dt).total_seconds(), 1)
        if duration < 1:
            return
        chunks.append({
            "start":            current["start"],
            "end":              end_ts_ist,
            "duration_seconds": duration,
            "app":              current["app"]        or "Unknown",
            "title":            current["title"]      or "",
            "afk_status":       current["afk_status"] or "unknown",
        })

    def open_chunk(ts_ist: str, app: str, title: str, afk: str):
        current["start"]      = ts_ist
        current["app"]        = app
        current["title"]      = title
        current["afk_status"] = afk

    while RUNNING:
        now_ts = now_ist()

        # Re-discover buckets if they appeared late
        if not win_bucket:
            win_bucket = find_bucket("aw-watcher-window_")
        if not afk_bucket:
            afk_bucket = find_bucket("aw-watcher-afk_")

        # Only fetch events that happened after this script started
        win_ev = latest_event(win_bucket, session_start_ist) if win_bucket else None
        afk_ev = latest_event(afk_bucket, session_start_ist) if afk_bucket else None

        app   = (win_ev or {}).get("data", {}).get("app",    "Unknown")
        title = (win_ev or {}).get("data", {}).get("title",  "")
        afk   = (afk_ev or {}).get("data", {}).get("status", "unknown")

        changed = (
            app   != current["app"]        or
            title != current["title"]      or
            afk   != current["afk_status"]
        )

        if changed:
            close_chunk(now_ts)
            save_chunks(chunks)
            open_chunk(now_ts, app, title, afk)
            print(f"[{now_ts}]  afk={afk:9s}  {app} — {title[:70]}")

        time.sleep(INTERVAL)

    # ── flush final open chunk on exit ─────────────────────────────
    close_chunk(now_ist())
    save_chunks(chunks)
    print(f"\nSaved {len(chunks)} chunks → {OUT_FILE}")


if __name__ == "__main__":
    main()