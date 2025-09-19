from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import subprocess
import threading
import sys
import platform
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Global state
monitoring_process = None
monitoring_active = False

# Ensure directories exist
os.makedirs('./details', exist_ok=True)

def get_python_executable():
    """Get the appropriate Python executable for the current platform."""
    # Use the same Python interpreter that's running this script
    return sys.executable

def get_interventions_script_path():
    """Get the proper path to interventions.py script."""
    # Use os.path.join for cross-platform path handling
    return os.path.join(os.getcwd(), 'src', 'interventions.py')

def start_interventions_process():
    """Start the interventions.py process with cross-platform compatibility."""
    try:
        python_exec = get_python_executable()
        script_path = get_interventions_script_path()
        
        # Verify the script exists
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"interventions.py not found at {script_path}")
        
        # Start the process with proper cross-platform handling
        if platform.system() == "Windows":
            # On Windows, we might need shell=True for some setups
            process = subprocess.Popen([
                python_exec, script_path
            ], cwd=os.getcwd(), shell=False)
        else:
            # On Unix-like systems (macOS, Linux)
            process = subprocess.Popen([
                python_exec, script_path
            ], cwd=os.getcwd())
        
        return process, None
        
    except FileNotFoundError as e:
        return None, f"Script not found: {str(e)}"
    except PermissionError as e:
        return None, f"Permission denied: {str(e)}"
    except Exception as e:
        return None, f"Failed to start interventions: {str(e)}"

@app.route('/api/save-task-details', methods=['POST'])
def save_task_details():
    """Save task details to JSON file and start interventions"""
    global monitoring_process, monitoring_active
    
    try:
        data = request.json
        
        # Extract required fields
        task_details = {
            'participantId': data.get('participantId'),
            'batch': data.get('batch'), 
            'category': data.get('category'),
            'taskDescription': data.get('taskDescription'),
            'name': data.get('name'),
            'estimatedTime': data.get('estimatedTime'),
            'timestamp': datetime.now().isoformat(),
            'startTime': data.get('startTime')
        }
        
        # Ensure details folder exists
        os.makedirs('./details', exist_ok=True)
        
        # Create filename with participant ID
        participant_id = data.get('participantId', 'unknown')
        details_file = f'./details/{participant_id}_task_details.json'
        
        # Load existing data or create new list
        existing_data = []
        if os.path.exists(details_file):
            try:
                with open(details_file, 'r') as f:
                    content = json.load(f)
                    # Handle both list format (new) and single object format (old)
                    if isinstance(content, list):
                        existing_data = content
                    else:
                        # Convert old single object format to list
                        existing_data = [content]
            except (json.JSONDecodeError, Exception) as e:
                print(f"Warning: Could not read existing file {details_file}: {e}")
                existing_data = []
        
        # Append new task details
        is_new_file = len(existing_data) == 0
        existing_data.append(task_details)
        
        # Save updated data
        with open(details_file, 'w') as f:
            json.dump(existing_data, f, indent=2)
        
        # Start interventions.py if not already running
        if not monitoring_active:
            process, error = start_interventions_process()
            if process:
                monitoring_process = process
                monitoring_active = True
                
                return jsonify({
                    'status': 'success',
                    'message': f'Task details {"created" if is_new_file else "appended"} and interventions started',
                    'interventionsStarted': True,
                    'isNewFile': is_new_file,
                    'totalEntries': len(existing_data),
                    'platform': platform.system(),
                    'python_executable': get_python_executable()
                })
            else:
                return jsonify({
                    'status': 'partial_success',
                    'message': f'Task details {"created" if is_new_file else "appended"} but failed to start interventions: {error}',
                    'interventionsStarted': False,
                    'isNewFile': is_new_file,
                    'totalEntries': len(existing_data),
                    'platform': platform.system(),
                    'python_executable': get_python_executable()
                })
        else:
            return jsonify({
                'status': 'success', 
                'message': f'Task details {"created" if is_new_file else "appended"} (interventions already running)',
                'interventionsStarted': False,
                'isNewFile': is_new_file,
                'totalEntries': len(existing_data)
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to save task details: {str(e)}'
        }), 500

def stop_interventions_process():
    """Stop the interventions process with cross-platform compatibility."""
    global monitoring_process, monitoring_active
    
    if not monitoring_active or not monitoring_process:
        return False, "No process running"
    
    try:
        # Check if process is still running
        if monitoring_process.poll() is None:
            # Process is still running, terminate it
            if platform.system() == "Windows":
                # On Windows, use terminate() and then kill() if needed
                monitoring_process.terminate()
                try:
                    monitoring_process.wait(timeout=5)  # Wait up to 5 seconds
                except subprocess.TimeoutExpired:
                    monitoring_process.kill()  # Force kill if it doesn't terminate
                    monitoring_process.wait()
            else:
                # On Unix-like systems, use terminate() and SIGKILL if needed
                monitoring_process.terminate()
                try:
                    monitoring_process.wait(timeout=5)  # Wait up to 5 seconds
                except subprocess.TimeoutExpired:
                    monitoring_process.kill()  # Force kill if it doesn't terminate
                    monitoring_process.wait()
        
        monitoring_process = None
        monitoring_active = False
        return True, "Process stopped successfully"
        
    except Exception as e:
        return False, f"Error stopping process: {str(e)}"

@app.route('/api/stop-interventions', methods=['POST'])
def stop_interventions():
    """Stop interventions.py process"""
    
    try:
        success, message = stop_interventions_process()
        
        if success:
            return jsonify({
                'status': 'success',
                'message': message,
                'platform': platform.system()
            })
        else:
            return jsonify({
                'status': 'warning',
                'message': message,
                'platform': platform.system()
            })
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': f'Error stopping interventions: {str(e)}',
            'platform': platform.system()
        }), 500

@app.route('/api/save-feedback', methods=['POST'])
def save_feedback():
    """Save feedback data to participant-specific JSON file"""
    try:
        data = request.json
        
        # Extract participant ID and create filename
        participant_id = data.get('participantId')
        if not participant_id:
            return jsonify({'status': 'error', 'message': 'Participant ID is required'}), 400
        
        # Ensure feedback directory exists
        feedback_dir = './feedback'
        os.makedirs(feedback_dir, exist_ok=True)
        
        # Create unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        filename = f"{participant_id}_feedback_{timestamp}.json"
        filepath = os.path.join(feedback_dir, filename)
        
        # Add server timestamp
        data['serverTimestamp'] = datetime.now().isoformat()
        
        # Save feedback data as individual file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({
            'status': 'success', 
            'message': 'Feedback saved successfully',
            'filename': filename
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save feedback: {str(e)}'}), 500

@app.route('/api/save-assessment', methods=['POST'])
def save_assessment():
    """Save assessment data to participant-specific JSON file"""
    try:
        data = request.json
        
        # Extract participant ID and create filename
        participant_id = data.get('participantId')
        if not participant_id:
            return jsonify({'status': 'error', 'message': 'Participant ID is required'}), 400
        
        # Ensure details directory exists
        details_dir = './details'
        os.makedirs(details_dir, exist_ok=True)
        
        # Create filename
        filename = f"{participant_id}_task_assessment.json"
        filepath = os.path.join(details_dir, filename)
        
        # Check if file exists and load existing data
        is_new_file = not os.path.exists(filepath)
        existing_data = []
        
        if not is_new_file:
            try:
                with open(filepath, 'r') as f:
                    existing_content = json.load(f)
                    # Ensure it's a list
                    if isinstance(existing_content, list):
                        existing_data = existing_content
                    else:
                        # Convert single object to list
                        existing_data = [existing_content]
            except (json.JSONDecodeError, FileNotFoundError):
                # If file is corrupted or doesn't exist, start fresh
                existing_data = []
                is_new_file = True
        
        # Add timestamp to the data
        data['timestamp'] = datetime.now().isoformat()
        
        # Append new entry
        existing_data.append(data)
        
        # Save updated data
        with open(filepath, 'w') as f:
            json.dump(existing_data, f, indent=2)
        
        return jsonify({
            'status': 'success', 
            'message': f'Assessment {"created" if is_new_file else "appended"} successfully',
            'isNewFile': is_new_file,
            'totalEntries': len(existing_data)
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save assessment: {str(e)}'}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current monitoring status"""
    global monitoring_process, monitoring_active
    
    # Check if process is actually still running
    if monitoring_active and monitoring_process:
        if monitoring_process.poll() is not None:
            # Process has terminated
            monitoring_active = False
            monitoring_process = None
    
    return jsonify({
        'monitoring_active': monitoring_active,
        'timestamp': datetime.now().isoformat(),
        'platform': platform.system(),
        'python_executable': get_python_executable(),
        'script_path': get_interventions_script_path(),
        'process_id': monitoring_process.pid if monitoring_process else None
    })

@app.route('/api/get-task-details', methods=['GET'])
def get_task_details():
    """Get current task details"""
    try:
        details_file = './details/task_details.json'
        if os.path.exists(details_file):
            with open(details_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint with platform information"""
    return jsonify({
        'status': 'healthy',
        'platform': platform.system(),
        'platform_version': platform.platform(),
        'python_version': sys.version,
        'python_executable': get_python_executable(),
        'script_path': get_interventions_script_path(),
        'script_exists': os.path.exists(get_interventions_script_path()),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print(f"Starting Cross-Platform API server on http://localhost:5000")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Python executable: {get_python_executable()}")
    print(f"Interventions script: {get_interventions_script_path()}")
    print(f"Script exists: {os.path.exists(get_interventions_script_path())}")
    print("\nEndpoints available:")
    print("  POST /api/save-task-details - Save task details and start interventions")
    print("  POST /api/stop-interventions - Stop interventions")
    print("  POST /api/save-assessment - Save task assessment data")
    print("  POST /api/save-feedback - Save real-time feedback")
    print("  GET /api/status - Get monitoring status")
    print("  GET /api/get-task-details - Get current task details")
    print("  GET /api/health - Health check with platform info")
    print("\nPress Ctrl+C to stop the server")
    app.run(debug=True, port=5000, host='0.0.0.0')
