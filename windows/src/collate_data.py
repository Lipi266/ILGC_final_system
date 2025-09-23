import json
import os
import time
from datetime import datetime
import signal

# Configuration
SCREENSHOT_FILE = "./screenshot/combined_captions.json"
WATCH_FILE = "./watch/watch_data.json"
INTERVENTIONS_FILE = "./interventions/interventions.json"
COLLATED_DIR = "./collated"
INTERVAL = 30  # seconds
RUNNING = True

def stop(*_):
    global RUNNING
    print("\nStopping collation...")
    RUNNING = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

def load_json_file(filepath):
    """Load JSON file safely, return empty dict if file doesn't exist or is invalid"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
    return {}

def get_last_entries(data, count):
    """Get the last N entries from different JSON structures"""
    if isinstance(data, dict):
        if 'entries' in data:
            # Watch data format
            entries = data.get('entries', [])
            return entries[-count:] if len(entries) >= count else entries
        else:
            # Screenshot captions format - convert to list of entries
            items = list(data.items())
            return [{"timestamp": k, "captions": v} for k, v in items[-count:]] if items else []
    return []

def load_intervention_data():
    """Load intervention data based on the specified rules"""
    try:
        if not os.path.exists(INTERVENTIONS_FILE):
            return []
        
        interventions = load_json_file(INTERVENTIONS_FILE)
        
        # If interventions is empty or not a list, return empty
        if not isinstance(interventions, list) or len(interventions) == 0:
            return []
        
        # If only 1 intervention exists, return it
        if len(interventions) == 1:
            return interventions
        
        # If 2 or more exist, return the last 2
        return interventions[-2:]
        
    except Exception as e:
        print(f"Error loading intervention data: {e}")
        return []

def collate_data():
    """Collate data from both sources and save to a new file"""
    try:
        # Load data from all sources
        screenshot_data = load_json_file(SCREENSHOT_FILE)
        watch_data = load_json_file(WATCH_FILE)
        intervention_data = load_intervention_data()
        
        # Get last entries
        last_screenshots = get_last_entries(screenshot_data, 6)
        last_watch = get_last_entries(watch_data, 2)
        
        # Create collated data structure
        timestamp = datetime.now()
        collated_data = {
            "collation_timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "collation_timestamp_iso": timestamp.isoformat(),
            "interval_seconds": INTERVAL,
            "data_sources": {
                "screenshot_entries": len(last_screenshots),
                "watch_entries": len(last_watch),
                "intervention_entries": len(intervention_data)
            },
            "screenshot_data": last_screenshots,
            "watch_data": last_watch,
            "intervention_data": intervention_data,
            "summary": {
                "screenshot_count": len(last_screenshots),
                "watch_count": len(last_watch),
                "intervention_count": len(intervention_data),
                "total_entries": len(last_screenshots) + len(last_watch) + len(intervention_data)
            }
        }
        
        # Create output directory
        os.makedirs(COLLATED_DIR, exist_ok=True)
        
        # Generate filename with timestamp
        filename = f"combined_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(COLLATED_DIR, filename)
        
        # Save collated data
        with open(filepath, 'w') as f:
            json.dump(collated_data, f, indent=2)
        
        print(f"Collated data saved: {filename}")
        print(f"  - Screenshot entries: {len(last_screenshots)}")
        print(f"  - Watch entries: {len(last_watch)}")
        print(f"  - Intervention entries: {len(intervention_data)}")
        
        return True
        
    except Exception as e:
        print(f"Error during collation: {e}")
        return False

def clear_existing_files():
    """Clear existing collated files when starting"""
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
    print(f"  - Screenshots: {SCREENSHOT_FILE}")
    print(f"  - Watch data: {WATCH_FILE}")
    print(f"  - Interventions: {INTERVENTIONS_FILE}")
    print(f"  - Output directory: {COLLATED_DIR}")
    print(f"  - Interval: {INTERVAL} seconds")
    print("Press Ctrl+C to stop.\n")
    
    # Clear existing files
    clear_existing_files()
    
    collation_count = 0
    next_collation = time.time() + INTERVAL
    
    while RUNNING:
        current_time = time.time()
        
        if current_time >= next_collation:
            collation_count += 1
            print(f"\n--- Collation #{collation_count} at {datetime.now().strftime('%H:%M:%S')} ---")
            
            if collate_data():
                print("Collation successful")
            else:
                print("Collation failed")
            
            # Schedule next collation
            next_collation = current_time + INTERVAL
            print(f"Next collation in {INTERVAL} seconds...")
        
        # Sleep for a short interval to avoid busy waiting
        time.sleep(1)
    
    print("Data collation service stopped.")

if __name__ == "__main__":
    main()
