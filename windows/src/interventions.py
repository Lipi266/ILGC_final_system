import os
import json
import time
import requests
from datetime import datetime
import logging
from dotenv import load_dotenv
import re
import ctypes
import platform
import threading

# Configuration
COLLATED_DIR = "./collated"
INTERVENTIONS_FILE = "./interventions/interventions.json"
INTERVAL = 65  # seconds

# Global variables for pause functionality
pause_until = None  # Timestamp when pause should end
pause_reason = None  # Reason for pause

# Import configuration (if available)
INTERVENTION_SERVER_URL = "http://10.1.45.59:8001/interventions"
TIMEOUT = 30

time.sleep(60)

# Logger setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("interventions")

# Load environment variables from .env file
load_dotenv()


def parse_duration_minutes(text):
    """Extract duration in minutes from text like '5 minutes', '10 min', etc."""
    if not text:
        return None
    
    # Look for patterns like "5 minutes", "10 min", "15 mins", "2-3 minutes", etc.
    patterns = [
        r'(\d+)\s*(?:minute|min)s?',  # "5 minutes", "10 min"
        r'(\d+)-\d+\s*(?:minute|min)s?',  # "2-3 minutes" - take first number
        r'(\d+)\s*(?:hr|hour)s?\s*(?:and\s*)?(\d+)?\s*(?:minute|min)s?',  # "1 hour 30 minutes"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        if matches:
            if isinstance(matches[0], tuple):
                # Handle hour + minutes pattern
                hours = int(matches[0][0]) if matches[0][0] else 0
                minutes = int(matches[0][1]) if matches[0][1] else 0
                return hours * 60 + minutes
            else:
                return int(matches[0])
    
    return None


def play_chime():
    """Play a system chime sound."""
    try:
        # Play Windows system sound
        ctypes.windll.user32.MessageBeep(0x40)  # MB_ICONASTERISK - pleasant chime
        time.sleep(0.2)
        ctypes.windll.user32.MessageBeep(0x40)  # Play twice for emphasis
        logger.info("Played chime - break period ended")
    except Exception as e:
        logger.error(f"Failed to play chime: {e}")


def check_for_off_screen_intervention(intervention_text, duration_text):
    """Check if intervention requires user to be off-screen and extract duration."""
    if not intervention_text:
        return False, None
    
    # Keywords that indicate off-screen interventions
    off_screen_keywords = [
        'take a break', 'step away', 'get up', 'walk around', 
        'leave your desk', 'stretch', 'rest your eyes',
        'take some time away', 'pause your work', 'brief break'
    ]
    
    intervention_lower = intervention_text.lower()
    is_off_screen = any(keyword in intervention_lower for keyword in off_screen_keywords)
    
    if is_off_screen and duration_text:
        duration_minutes = parse_duration_minutes(duration_text)
        return True, duration_minutes
    
    return False, None


def set_monitoring_pause(duration_minutes, reason):
    """Set a pause for monitoring for the specified duration."""
    global pause_until, pause_reason
    
    if duration_minutes and duration_minutes > 0:
        pause_until = datetime.now().timestamp() + (duration_minutes * 60)
        pause_reason = reason
        logger.info(f"Monitoring paused for {duration_minutes} minutes. Reason: {reason}")
        return True
    return False


def is_monitoring_paused():
    """Check if monitoring is currently paused."""
    global pause_until, pause_reason
    
    if pause_until is None:
        return False
    
    current_time = datetime.now().timestamp()
    if current_time >= pause_until:
        # Pause period has ended
        logger.info(f"Monitoring pause ended. Previous reason: {pause_reason}")
        play_chime()  # Play chime when break ends
        pause_until = None
        pause_reason = None
        return False
    
    return True


def clear_interventions_file():
    """Clear the interventions.json file at the start of each run."""
    try:
        os.makedirs(os.path.dirname(INTERVENTIONS_FILE), exist_ok=True)
        with open(INTERVENTIONS_FILE, "w") as f:
            json.dump([], f, indent=2)
        logger.info("Cleared interventions.json file")
    except Exception as e:
        logger.error(f"Error clearing interventions.json file: {e}")


def load_task_details():
    """Load the latest task details from participant-specific files."""
    try:
        details_dir = "./details"
        if not os.path.exists(details_dir):
            logger.warning("Details directory not found. Using default task.")
            return {
                "category": "general work",
                "taskDescription": "general work task",
                "participantId": "Unknown",
                "batch": "Unknown",
            }

        # Find participant-specific task details files
        task_files = [
            f for f in os.listdir(details_dir) if f.endswith("_task_details.json")
        ]

        if not task_files:
            logger.warning(
                "No participant-specific task details files found. Using default task."
            )
            return {
                "category": "general work",
                "taskDescription": "general work task",
                "participantId": "Unknown",
                "batch": "Unknown",
            }

        # Get the most recently modified file
        latest_file = max(
            (os.path.join(details_dir, f) for f in task_files), key=os.path.getmtime
        )

        with open(latest_file, "r") as f:
            task_data = json.load(f)

            # Handle both list format (new) and single object format (old)
            if isinstance(task_data, list):
                if task_data:
                    # Use the latest entry (last in the list)
                    latest_entry = task_data[-1]
                    logger.info(
                        f"Loaded latest task details for participant {latest_entry.get('participantId', 'Unknown')} from {latest_file} (entry {len(task_data)} of {len(task_data)})"
                    )
                    return latest_entry
                else:
                    logger.warning(f"Task details file {latest_file} is empty.")
                    return {
                        "category": "general work",
                        "taskDescription": "general work task",
                        "participantId": "Unknown",
                        "batch": "Unknown",
                    }
            else:
                # Single object format (old style)
                logger.info(
                    f"Loaded task details for participant {task_data.get('participantId', 'Unknown')} from {latest_file}"
                )
                return task_data

    except Exception as e:
        logger.error(f"Error loading task details: {e}")
        return {
            "category": "general work",
            "taskDescription": "general work task",
            "participantId": "Unknown",
            "batch": "Unknown",
        }


def load_latest_collated_file():
    """Load the latest JSON file from the collated directory."""
    try:
        files = [f for f in os.listdir(COLLATED_DIR) if f.endswith(".json")]
        if not files:
            logger.warning("No collated files found.")
            return None

        # Get the latest file based on modification time
        latest_file = max(
            (os.path.join(COLLATED_DIR, f) for f in files), key=os.path.getmtime
        )
        with open(latest_file, "r") as f:
            logger.info(f"Loaded latest collated file: {latest_file}")
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading latest collated file: {e}")
        return None


import json


def simplify_data_for_api(data):
    """Simplify the collated data for the OpenAI API."""

    # If data is a JSON string, parse it
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("String data is not valid JSON")

    # Normalize to a list of dicts
    if isinstance(data, dict):
        data_items = [data]
    elif isinstance(data, list):
        data_items = data
    else:
        raise ValueError(f"Unexpected data type: {type(data)}")

    simplified_data = []
    result = {"monitoring_data": simplified_data}

    for entry in data_items:
        if isinstance(entry, str):  # defensive: if any entry is a JSON string
            try:
                entry = json.loads(entry)
            except json.JSONDecodeError:
                continue  # skip invalid entries

        if not isinstance(entry, dict):
            continue  # skip weird entries

        screenshot_data = entry.get("screenshot_data", [])
        watch_data = entry.get("watch_data", [])
        feedback_data = entry.get("feedback_data")
        intervention_data = entry.get("intervention_data", [])

        # Monitoring data
        for screenshot, watch in zip(screenshot_data, watch_data):
            simplified_data.append(
                {
                    "screenshot_caption": screenshot["captions"]["screenshot_caption"],
                    "webcam_caption": screenshot["captions"]["webcam_caption"],
                    "stress_level": watch["watch_data"]["stress_level"],
                    "interpretation": watch["watch_data"]["interpretation"],
                }
            )

        # Feedback data
        if feedback_data:
            result["user_feedback"] = {
                "type": feedback_data.get("feedbackType"),
                "text": feedback_data.get("feedbackText", ""),
                "timestamp": feedback_data.get("timestamp"),
                "elapsed_time_seconds": feedback_data.get("elapsedTime", 0),
            }

        # Interventions
        if intervention_data:
            if "previous_interventions" not in result:
                result["previous_interventions"] = []
            for intervention in intervention_data:
                structured = intervention.get("structured_analysis", {})
                result["previous_interventions"].append(
                    {
                        "timestamp": intervention.get("timestamp"),
                        "was_distracted": structured.get("distracted", "UNKNOWN"),
                        "distraction_type": structured.get("distraction_type", ""),
                        "intervention_given": structured.get("intervention", "FALSE"),
                        "intervention_scale": structured.get("intervention_scale", ""),
                        "confidence": structured.get("confidence", ""),
                    }
                )

    return result


import re

def parse_analysis_response(response_text: str) -> dict:
    """Parse the response text into a structured format.
    Works with or without markdown-style **key** formatting."""

    try:
        # Regex patterns allow optional ** around the keys
        distracted_match = re.search(
            r"(?:\*\*)?Distracted(?:\*\*)?: (YES|NO)", response_text, re.I
        )
        confidence_match = re.search(
            r"(?:\*\*)?Confidence(?:\*\*)?: (High|Medium|Low)", response_text, re.I
        )
        distraction_type_match = re.search(
            r"(?:\*\*)?Distraction Type(?:\*\*)?: (.+)", response_text, re.I
        )
        detailed_reasoning_match = re.search(
            r"(?:\*\*)?Detailed Reasoning(?:\*\*)?: (.+?)(?=(?:\*\*)?Intervention(?:\*\*)?:|\Z)",
            response_text,
            re.S | re.I,
        )
        intervention_match = re.search(
            r"(?:\*\*)?Intervention(?:\*\*)?: (.+)", response_text, re.I
        )
        intervention_scale_match = re.search(
            r"(?:\*\*)?Intervention Scale(?:\*\*)?: (Easy|Medium|Low|High|FALSE)",
            response_text,
            re.I,
        )
        duration_match = re.search(
            r"(?:\*\*)?Duration(?:\*\*)?: (.+)", response_text, re.I
        )

        structured_analysis = {
            "distracted": (
                distracted_match.group(1).upper() == "YES"
                if distracted_match
                else False
            ),
            "confidence": (
                confidence_match.group(1).capitalize()
                if confidence_match
                else "Unknown"
            ),
            "distraction_type": (
                distraction_type_match.group(1).strip()
                if distraction_type_match
                else "Unknown"
            ),
            "detailed_reasoning": (
                detailed_reasoning_match.group(1).strip()
                if detailed_reasoning_match
                else "No reasoning provided"
            ),
            "intervention": (
                intervention_match.group(1).strip() if intervention_match else "FALSE"
            ),
            "intervention_scale": (
                intervention_scale_match.group(1).strip()
                if intervention_scale_match
                else "FALSE"
            ),
            "duration": (
                duration_match.group(1).strip() if duration_match else "FALSE"
            ),
        }

        return structured_analysis
    except Exception:
        return {"error": "parse_error"}


    except Exception as e:
        logger.error(f"Error parsing analysis response: {e}")
        return {"error": "Failed to parse response"}


def analyze_distraction(data):
    """Send sensor and task data to intervention server for distraction analysis."""
    # Load task details
    task_details = load_task_details()

    # Handle category as either string (legacy) or array (new multiple selection)
    category_data = task_details.get("category", "general work")
    if isinstance(category_data, list):
        task_category = " and ".join(category_data) if category_data else "general work"
    else:
        task_category = category_data

    task_description = task_details.get("taskDescription", "general work task")
    participant_id = task_details.get("participantId", "Unknown")
    system_type = task_details.get("systemType", "system2")  # Default to system2 if not specified

    print(f"Task: {task_category}, desc: {task_description}, system: {system_type}")

    # If System 1 (control), skip server analysis and return mock analysis
    if system_type == "system1":
        logger.info("System 1 (control) mode - skipping server analysis")
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "participant_id": participant_id,
            "task_category": task_category,
            "task_description": task_description,
            "raw_analysis": "*Distracted: NO (Control Group - No Analysis)\n**Confidence: N/A\n**Distraction Type: N/A\n**Detailed Reasoning: Control group participant - monitoring only, no interventions provided.\n**Intervention: FALSE\n**Intervention Scale: FALSE\n*Duration: FALSE",
            "structured_analysis": {
                "distracted": False,
                "confidence": "N/A",
                "distraction_type": "N/A",
                "detailed_reasoning": "Control group participant - monitoring only, no interventions provided.",
                "intervention": "FALSE",
                "intervention_scale": "FALSE",
                "duration": "FALSE"
            },
            "api_response": "control_group",
            "server_used": "none",
        }

    # Prepare the payload for the intervention server (System 2 only)
    simplified_data = simplify_data_for_api(data)

    payload = {
        "participant_id": participant_id,
        "task_category": task_category,
        "task_description": task_description,
        "monitoring_data": simplified_data.get("monitoring_data", []),
        "user_feedback": simplified_data.get("user_feedback"),
        "previous_interventions": simplified_data.get("previous_interventions", []),
    }

    try:
        response = requests.post(
            INTERVENTION_SERVER_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            result = response.json()

            # Prefer structured response; otherwise try to parse text
            if "structured_analysis" in result:
                parsed_analysis = result["structured_analysis"]
                analysis_text = result.get("raw_analysis", "Server analysis completed")
            elif "distracted" in result:
                parsed_analysis = result
                analysis_text = result.get("raw_analysis", "Server analysis completed")
            else:
                analysis_text = result.get("analysis", str(result))
                parsed_analysis = parse_analysis_response(analysis_text)

            # Debug logging
            logger.info(f"Server response analysis: distracted={parsed_analysis.get('distracted', 'unknown')}, intervention={parsed_analysis.get('intervention', 'unknown')}")

            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "participant_id": participant_id,
                "task_category": task_category,
                "task_description": task_description,
                "raw_analysis": analysis_text,
                "structured_analysis": parsed_analysis,
                "api_response": "success",
                "server_used": "intervention_server",
            }
        else:
            logger.error(
                f"Intervention server request failed: {response.status_code} - {response.text}"
            )
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "participant_id": participant_id,
                "task_category": task_category,
                "task_description": task_description,
                "error": f"Intervention server request failed: {response.status_code}",
                "api_response": "error",
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to intervention server: {e}")
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "participant_id": participant_id,
            "task_category": task_category,
            "task_description": task_description,
            "error": f"Error connecting to intervention server: {e}",
            "api_response": "error",
        }
    except Exception as e:
        logger.error(f"Unexpected error in intervention analysis: {e}")
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "participant_id": participant_id,
            "task_category": task_category,
            "task_description": task_description,
            "error": f"Unexpected error: {e}",
            "api_response": "error",
        }


# Client no longer performs OpenAI analysis or fallback; server owns prompts and analysis.


def show_intervention_popup(intervention):
    """Display a reliable Windows MessageBox with sound and forced foreground."""
    try:
        # Use Windows MessageBox API directly for maximum reliability
        import ctypes
        from ctypes import wintypes
        
        # Play system sound first to get attention
        try:
            # Play the Windows "Critical Stop" sound
            ctypes.windll.user32.MessageBeep(0x10)  # MB_ICONHAND sound
            time.sleep(0.1)  # Brief pause
            # Play it again for emphasis
            ctypes.windll.user32.MessageBeep(0x10)
        except:
            pass  # If sound fails, continue anyway
        
        # Force the current process to foreground first
        try:
            # Get current process window
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            
            # Get current thread and process IDs
            current_thread_id = kernel32.GetCurrentThreadId()
            current_process_id = kernel32.GetCurrentProcessId()
            
            # Try to force foreground
            user32.SetForegroundWindow(user32.GetDesktopWindow())
            user32.AllowSetForegroundWindow(current_process_id)
            
        except:
            pass  # If foreground forcing fails, continue anyway
        
        # Define MessageBox constants
        MB_YESNO = 0x4
        MB_ICONQUESTION = 0x20
        MB_TOPMOST = 0x40000
        MB_SETFOREGROUND = 0x10000
        MB_SYSTEMMODAL = 0x1000  # System modal - blocks everything
        
        # Combine flags for maximum visibility
        flags = MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND | MB_SYSTEMMODAL
        
        # Prepare the message
        title = "🚨 URGENT: Workplace Distraction Alert 🚨"
        message = f"⚠️ ATTENTION REQUIRED ⚠️\n\nINTERVENTION:\n{intervention}\n\nWas this intervention helpful?\n\n✅ Click YES if helpful\n❌ Click NO if not helpful"
        
        # Flash the screen to get attention
        try:
            ctypes.windll.user32.FlashWindow(user32.GetDesktopWindow(), True)
        except:
            pass
        
        # Call Windows MessageBox API
        result = ctypes.windll.user32.MessageBoxW(
            0,  # Parent window handle (0 = no parent)
            message,
            title,
            flags
        )
        
        # MessageBox returns 6 for Yes, 7 for No
        if result == 6:  # IDYES
            feedback = "helpful"
        elif result == 7:  # IDNO
            feedback = "not_helpful"
        else:
            feedback = "no_response"
        
        logger.info(f"Intervention popup completed with feedback: {feedback}")
        return feedback
        
    except Exception as e:
        logger.error(f"Error displaying Windows MessageBox: {e}")
        
        # Fallback to simple print statement and auto-response
        try:
            print(f"\n{'='*60}")
            print(f"🚨 WORKPLACE DISTRACTION ALERT 🚨")
            print(f"{'='*60}")
            print(f"INTERVENTION: {intervention}")
            print(f"{'='*60}")
            print("Note: Popup failed, automatically marking as 'helpful' for data collection")
            print(f"{'='*60}\n")
            
            # Auto-respond as helpful to keep data collection going
            logger.info("Popup failed, auto-responding as 'helpful'")
            return "helpful"
            
        except Exception as e2:
            logger.error(f"Even fallback print failed: {e2}")
            return "error"


def append_to_interventions_file(data):
    """Append the analysis result to the interventions.json file."""
    try:
        os.makedirs(os.path.dirname(INTERVENTIONS_FILE), exist_ok=True)
        if os.path.exists(INTERVENTIONS_FILE):
            with open(INTERVENTIONS_FILE, "r") as f:
                interventions = json.load(f)
        else:
            interventions = []

        interventions.append(data)

        with open(INTERVENTIONS_FILE, "w") as f:
            json.dump(interventions, f, indent=2)

        logger.info("Appended analysis result to interventions.json")

        # Show popup if distracted is True and system is system2
        # Load system type from task details since we removed it from intervention data
        task_details = load_task_details()
        system_type = task_details.get("systemType", "system2")
        intervention = data["structured_analysis"].get("intervention", "FALSE")
        distracted = data["structured_analysis"].get("distracted", False)
        
        logger.info(f"Checking intervention popup conditions: system_type={system_type}, distracted={distracted}, intervention={intervention}")
        
        # Show popup if either distracted is True OR intervention is not FALSE, and system is system2
        should_show_popup = (distracted == True or intervention != "FALSE") and system_type == "system2"
        
        if should_show_popup:
            # Use intervention text if available, otherwise create a generic distraction message
            popup_message = intervention if intervention != "FALSE" else "You appear to be distracted. Please refocus on your task."
            logger.info(f"Showing intervention popup for: {popup_message}")
            
            # Check if this is an off-screen intervention with duration
            duration_text = data["structured_analysis"].get("duration", "")
            is_off_screen, duration_minutes = check_for_off_screen_intervention(intervention, duration_text)
            
            user_feedback = show_intervention_popup(popup_message)
            
            # If it's an off-screen intervention with duration, set monitoring pause
            if is_off_screen and duration_minutes:
                pause_set = set_monitoring_pause(duration_minutes, f"Off-screen intervention: {intervention}")
                if pause_set:
                    logger.info(f"Set monitoring pause for {duration_minutes} minutes due to off-screen intervention")
            
            # Add user feedback to the data
            data["user_feedback"] = user_feedback
            
            # Re-save the updated data with user feedback
            interventions[-1] = data  # Update the last entry with feedback
            with open(INTERVENTIONS_FILE, "w") as f:
                json.dump(interventions, f, indent=2)
            
            logger.info(f"Added user feedback '{user_feedback}' to interventions.json")
        elif system_type == "system1":
            logger.info("System 1 (control) - intervention popup suppressed")
        else:
            logger.info(f"No intervention popup needed - distracted={distracted}, intervention={intervention}, system_type={system_type}")
    except Exception as e:
        logger.error(f"Error appending to interventions file: {e}")


def main():
    print("Starting distraction analysis service...")
    print(f"Monitoring collated files in: {COLLATED_DIR}")
    print(f"Results will be saved to: {INTERVENTIONS_FILE}")
    print(f"Analysis interval: {INTERVAL} seconds")
    print("Press Ctrl+C to stop.\n")

    # Clear interventions.json at the start
    clear_interventions_file()

    while True:
        # Check if monitoring is paused
        if is_monitoring_paused():
            logger.info(f"Monitoring paused: {pause_reason}. Skipping data collection.")
            time.sleep(INTERVAL)
            continue
        
        # Load the latest collated file
        collated_data = load_latest_collated_file()
        if collated_data:
            # Analyze the data
            analysis_result = analyze_distraction(collated_data)

            # Append the result to interventions.json
            append_to_interventions_file(analysis_result)

        # Wait for the next interval
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
