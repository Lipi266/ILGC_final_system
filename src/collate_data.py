import json
import os
import time
from datetime import datetime
import signal

# Configuration
SCREENSHOT_FILE = "./screenshot/combined_captions.json"
WATCH_FILE = "./watch/watch_data.json"
FEEDBACK_DIR = "./feedback"
INTERVENTIONS_FILE = "./interventions/interventions.json"
COLLATED_DIR = "./collated"
PROCESSED_FEEDBACK_FILE = "./collated/.processed_feedback.json"
INTERVAL = 65  # seconds
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

def load_processed_feedback():
    """Load the list of already processed feedback files"""
    try:
        if os.path.exists(PROCESSED_FEEDBACK_FILE):
            with open(PROCESSED_FEEDBACK_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading processed feedback list: {e}")
    return []

def save_processed_feedback(processed_files):
    """Save the list of processed feedback files"""
    try:
        os.makedirs(os.path.dirname(PROCESSED_FEEDBACK_FILE), exist_ok=True)
        with open(PROCESSED_FEEDBACK_FILE, 'w') as f:
            json.dump(processed_files, f, indent=2)
    except Exception as e:
        print(f"Error saving processed feedback list: {e}")

def get_new_feedback_files():
    """Get feedback files that haven't been processed yet"""
    if not os.path.exists(FEEDBACK_DIR):
        return []
    
    try:
        processed_files = load_processed_feedback()
        all_feedback_files = [f for f in os.listdir(FEEDBACK_DIR) if f.endswith('.json')]
        new_files = [f for f in all_feedback_files if f not in processed_files]
        
        # Sort by creation time to get the latest first
        new_files_with_time = []
        for filename in new_files:
            filepath = os.path.join(FEEDBACK_DIR, filename)
            try:
                mtime = os.path.getmtime(filepath)
                new_files_with_time.append((filename, mtime))
            except OSError:
                continue
        
        # Sort by modification time (newest first) and return just filenames
        new_files_with_time.sort(key=lambda x: x[1], reverse=True)
        return [filename for filename, _ in new_files_with_time]
        
    except Exception as e:
        print(f"Error getting new feedback files: {e}")
        return []

def load_latest_feedback():
    """Load the latest feedback file that hasn't been processed"""
    new_feedback_files = get_new_feedback_files()
    
    if not new_feedback_files:
        return None, None
    
    # Get the latest (first in sorted list) feedback file
    latest_file = new_feedback_files[0]
    filepath = os.path.join(FEEDBACK_DIR, latest_file)
    
    try:
        with open(filepath, 'r') as f:
            feedback_data = json.load(f)
            return feedback_data, latest_file
    except Exception as e:
        print(f"Error loading feedback file {latest_file}: {e}")
        return None, None

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
        
        # Check for new feedback
        feedback_data, feedback_filename = load_latest_feedback()
        
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
                "intervention_entries": len(intervention_data),
                "feedback_included": feedback_data is not None
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
        
        # Add feedback data if available
        if feedback_data and feedback_filename:
            collated_data["feedback_data"] = feedback_data
            collated_data["feedback_filename"] = feedback_filename
            collated_data["summary"]["has_feedback"] = True
            print(f"Including new feedback: {feedback_filename}")
        else:
            collated_data["summary"]["has_feedback"] = False
        
        # Create output directory
        os.makedirs(COLLATED_DIR, exist_ok=True)
        
        # Generate filename with timestamp
        filename = f"combined_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(COLLATED_DIR, filename)
        
        # Save collated data
        with open(filepath, 'w') as f:
            json.dump(collated_data, f, indent=2)
        
        # Mark feedback as processed if it was included
        if feedback_filename:
            processed_files = load_processed_feedback()
            processed_files.append(feedback_filename)
            save_processed_feedback(processed_files)
        
        print(f"Collated data saved: {filename}")
        print(f"  - Screenshot entries: {len(last_screenshots)}")
        print(f"  - Watch entries: {len(last_watch)}")
        print(f"  - Intervention entries: {len(intervention_data)}")
        if feedback_data:
            feedback_type = feedback_data.get('feedbackType', 'unknown')
            print(f"  - Feedback: {feedback_type} feedback included")
        
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
        
        # Reset processed feedback tracking
        save_processed_feedback([])
        
        print("Cleared existing collated files and reset feedback tracking")
    except Exception as e:
        print(f"Error clearing files: {e}")

def main():
    print("Starting data collation service...")
    print(f"Monitoring:")
    print(f"  - Screenshots: {SCREENSHOT_FILE}")
    print(f"  - Watch data: {WATCH_FILE}")
    print(f"  - Interventions: {INTERVENTIONS_FILE}")
    print(f"  - Feedback directory: {FEEDBACK_DIR}")
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
