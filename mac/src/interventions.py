import os
import json
import time
import requests
from datetime import datetime
import logging
from dotenv import load_dotenv
# from plyer import notification
import subprocess
import re

# Configuration
COLLATED_DIR = "./collated"
INTERVENTIONS_FILE = "./interventions/interventions.json"
INTERVAL = 65  # seconds

# Import configuration (if available)
INTERVENTION_SERVER_URL = "http://10.1.45.59:8001/interventions"
TIMEOUT = 30

time.sleep(60)

# Logger setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("interventions")

# Load environment variables from .env file
load_dotenv()


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
        }

        return structured_analysis

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

    # Prepare the payload for the intervention server
    simplified_data = simplify_data_for_api(data)

    payload = {
        "participant_id": participant_id,
        "task_category": task_category,
        "task_description": task_description,
        "monitoring_data": simplified_data.get("monitoring_data", []),
        "user_feedback": simplified_data.get("user_feedback"),
        "previous_interventions": simplified_data.get("previous_interventions", []),
    }

    print(f"Task: {task_category}, desc: {task_description}")

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
                "error": f"Intervention server request failed: {response.status_code}",
                "api_response": "error",
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to intervention server: {e}")
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": f"Error connecting to intervention server: {e}",
            "api_response": "error",
        }
    except Exception as e:
        logger.error(f"Unexpected error in intervention analysis: {e}")
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": f"Unexpected error: {e}",
            "api_response": "error",
        }


# Client no longer performs OpenAI analysis or fallback; server owns prompts and analysis.

def show_intervention_popup(intervention):
    """Display a macOS system notification with the intervention text using osascript."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{intervention}" with title "Intervention Required"'
        ])
        logger.info("Displayed intervention notification")
    except Exception as e:
        logger.error(f"Error displaying intervention notification: {e}")

# def show_intervention_popup(intervention):
#     """Display a system notification with the intervention text."""
#     try:
#         notification.notify(
#             title="Intervention Required",
#             message=intervention,
#             app_name="Distraction Analysis",
#             timeout=10,  # Notification will disappear after 10 seconds
#         )
#         logger.info("Displayed intervention notification")
#     except Exception as e:
#         logger.error(f"Error displaying intervention notification: {e}")


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

        # Show popup if intervention is not FALSE
        intervention = data["structured_analysis"].get("intervention", "FALSE")
        if intervention != "FALSE":
            show_intervention_popup(intervention)
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
