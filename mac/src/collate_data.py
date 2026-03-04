import json
import os
import time
from datetime import datetime
import signal

# Configuration
base_dir = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_FILE   = "./screenshot/combined_captions.json"
WATCH_FILE        = "./watch/watch_data.json"
INTERVENTIONS_FILE = "./interventions/interventions.json"
AW_FILE           = "./activityTracker/activity.json"   # ← ActivityWatch data
COLLATED_DIR      = os.path.join(base_dir, "..", "collated")
os.makedirs(COLLATED_DIR, exist_ok=True)
INTERVAL = 60  # seconds
RUNNING  = True

def stop(*_):
    global RUNNING
    print("\nStopping collation...")
    RUNNING = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def load_json_file(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
    return {}


def get_last_entries(data, count):
    if isinstance(data, dict):
        if 'entries' in data:
            entries = data.get('entries', [])
            return entries[-count:] if len(entries) >= count else entries
        else:
            items = list(data.items())
            return [{"timestamp": k, "captions": v} for k, v in items[-count:]] if items else []
    return []


def get_recent_aw_chunks(data, count=10):
    """
    Return the last `count` AW chunks.
    Strips out any afk chunks to reduce noise — GPT only needs
    what the user was actually doing on screen.
    """
    if not isinstance(data, dict):
        return []
    chunks = data.get("chunks", [])
    # Keep all chunks (including afk) so GPT has full picture,
    # but trim to last `count` entries to avoid token bloat
    return chunks[-count:] if len(chunks) >= count else chunks


def load_intervention_data():
    try:
        if not os.path.exists(INTERVENTIONS_FILE):
            return []
        interventions = load_json_file(INTERVENTIONS_FILE)
        if not isinstance(interventions, list) or len(interventions) == 0:
            return []
        if len(interventions) <= 3:
            return interventions
        return interventions[-4:]
    except Exception as e:
        print(f"Error loading intervention data: {e}")
        return []


def collate_data():
    try:
        screenshot_data  = load_json_file(SCREENSHOT_FILE)
        watch_data       = load_json_file(WATCH_FILE)
        intervention_data = load_intervention_data()
        aw_data          = load_json_file(AW_FILE)           # ← load AW

        last_screenshots = get_last_entries(screenshot_data, 6)
        last_watch       = get_last_entries(watch_data, 2)
        last_aw_chunks   = get_recent_aw_chunks(aw_data, 10)  # ← last 10 chunks

        timestamp = datetime.now()
        collated_data = {
            "collation_timestamp":     timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "collation_timestamp_iso": timestamp.isoformat(),
            "interval_seconds":        INTERVAL,
            "data_sources": {
                "screenshot_entries":    len(last_screenshots),
                "watch_entries":         len(last_watch),
                "intervention_entries":  len(intervention_data),
                "aw_chunks":             len(last_aw_chunks),   # ← added
            },
            "screenshot_data":    last_screenshots,
            "watch_data":         last_watch,
            "intervention_data":  intervention_data,
            "aw_data":            last_aw_chunks,               # ← added
            "summary": {
                "screenshot_count":    len(last_screenshots),
                "watch_count":         len(last_watch),
                "intervention_count":  len(intervention_data),
                "aw_count":            len(last_aw_chunks),     # ← added
                "total_entries":       len(last_screenshots) + len(last_watch) + len(intervention_data) + len(last_aw_chunks),
            }
        }

        os.makedirs(COLLATED_DIR, exist_ok=True)
        filename = f"combined_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(COLLATED_DIR, filename)

        with open(filepath, 'w') as f:
            json.dump(collated_data, f, indent=2)

        print(f"Collated data saved: {filename}")
        print(f"  - Screenshot entries : {len(last_screenshots)}")
        print(f"  - Watch entries      : {len(last_watch)}")
        print(f"  - Intervention entries: {len(intervention_data)}")
        print(f"  - AW chunks          : {len(last_aw_chunks)}")
        return True

    except Exception as e:
        print(f"Error during collation: {e}")
        return False


def clear_existing_files():
    try:
        if os.path.exists(COLLATED_DIR):
            for file in os.listdir(COLLATED_DIR):
                if file.startswith("combined_") and file.endswith(".json"):
                    os.remove(os.path.join(COLLATED_DIR, file))
                    print(f"Removed existing file: {file}")
        else:
            os.makedirs(COLLATED_DIR, exist_ok=True)
        print("Cleared existing collated files")
    except Exception as e:
        print(f"Error clearing files: {e}")


def main():
    print("Starting data collation service...")
    print(f"Monitoring:")
    print(f"  - Screenshots  : {SCREENSHOT_FILE}")
    print(f"  - Watch data   : {WATCH_FILE}")
    print(f"  - Interventions: {INTERVENTIONS_FILE}")
    print(f"  - ActivityWatch: {AW_FILE}")
    print(f"  - Output dir   : {COLLATED_DIR}")
    print(f"  - Interval     : {INTERVAL} seconds")
    print("Press Ctrl+C to stop.\n")

    clear_existing_files()

    collation_count = 0
    next_collation  = time.time() + INTERVAL

    while RUNNING:
        if time.time() >= next_collation:
            collation_count += 1
            print(f"\n--- Collation #{collation_count} at {datetime.now().strftime('%H:%M:%S')} ---")
            collate_data()
            next_collation = time.time() + INTERVAL
            print(f"Next collation in {INTERVAL} seconds...")
        time.sleep(1)

    print("Data collation service stopped.")


if __name__ == "__main__":
    main()