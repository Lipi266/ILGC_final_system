import json, time, requests, os, signal
from datetime import datetime, timedelta
import glob

API_URL = "http://localhost:5600/api/0/export"
DATA_DIR = "./activityTracker"
RAW_FILE = os.path.join(DATA_DIR, "raw.json")
PROCESSED_FILE = os.path.join(DATA_DIR, "processed.json")
INTERVAL = 10
RUNNING = True

def stop(*_):
    global RUNNING
    print("\nStopping...")
    RUNNING = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

def clear_existing_data():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
        for file in json_files:
            os.remove(file)
            print(f"Deleted: {file}")
        if json_files:
            print("Cleared existing JSON files")
    except Exception as e:
        print("Error clearing files:", e)

def fetch_data():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        with open(RAW_FILE, "w") as f:
            json.dump(r.json(), f)
        print("Fetched data")
        return True
    except Exception as e:
        print("Fetch failed:", e)
        return False

def load_raw():
    if os.path.exists(RAW_FILE):
        with open(RAW_FILE) as f:
            return json.load(f)
    return {}

def events_to_chunks(events):
    chunks = []
    for ev in events:
        ts = datetime.fromisoformat(ev["timestamp"].replace("Z","+00:00"))
        dur = ev.get("duration", 0)
        if dur < 1:  
            continue
        chunks.append({
            "start": ts.isoformat(),
            "end": (ts + timedelta(seconds=dur)).isoformat(),
            "duration_miliseconds": dur,
            "app": ev.get("data", {}).get("app", "Unknown"),
            "title": ev.get("data", {}).get("title", "")
        })
    return chunks

def process_data():
    raw = load_raw()
    chunks = []
    for bdata in raw.get("buckets", {}).values():
        chunks.extend(events_to_chunks(bdata.get("events", [])))
    out = {"last_updated": datetime.now().isoformat(), "chunks": chunks}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROCESSED_FILE, "w") as f:
        json.dump(out, f, indent=2)
    print("Processed ->", PROCESSED_FILE)

print("Starting monitor... Ctrl+C to stop.")
clear_existing_data()
while RUNNING:
    if fetch_data():
        process_data()
    time.sleep(INTERVAL)
