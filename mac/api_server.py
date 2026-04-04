from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import subprocess
import signal
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
    return sys.executable

def get_interventions_script_path():
    return os.path.join(os.getcwd(), 'src', 'interventions.py')

def start_interventions_process():
    """Start interventions.py in its own process group so it can be cleanly killed."""
    try:
        python_exec = get_python_executable()
        script_path = get_interventions_script_path()

        if not os.path.exists(script_path):
            raise FileNotFoundError(f"interventions.py not found at {script_path}")

        if platform.system() == "Windows":
            process = subprocess.Popen(
                [python_exec, script_path],
                cwd=os.getcwd(),
                shell=False,
            )
        else:
            # setsid puts interventions.py in its own session/process-group.
            # This means pkill or kill(-pgid) in the cleanup script will
            # reach it even after api_server exits.
            process = subprocess.Popen(
                [python_exec, script_path],
                cwd=os.getcwd(),
                preexec_fn=os.setsid,   # <-- key fix
            )

        return process, None

    except FileNotFoundError as e:
        return None, f"Script not found: {str(e)}"
    except PermissionError as e:
        return None, f"Permission denied: {str(e)}"
    except Exception as e:
        return None, f"Failed to start interventions: {str(e)}"


def stop_interventions_process():
    """Stop interventions.py and its entire process group."""
    global monitoring_process, monitoring_active

    if not monitoring_active or not monitoring_process:
        return False, "No process running"

    try:
        if monitoring_process.poll() is None:
            if platform.system() == "Windows":
                monitoring_process.terminate()
                try:
                    monitoring_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    monitoring_process.kill()
                    monitoring_process.wait()
            else:
                # Kill the entire process group (includes any children spawned by interventions.py)
                try:
                    pgid = os.getpgid(monitoring_process.pid)
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    monitoring_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        pgid = os.getpgid(monitoring_process.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    monitoring_process.wait()

        monitoring_process = None
        monitoring_active = False
        return True, "Process stopped successfully"

    except Exception as e:
        monitoring_process = None
        monitoring_active = False
        return False, f"Error stopping process: {str(e)}"


@app.route('/api/save-task-details', methods=['POST'])
def save_task_details():
    global monitoring_process, monitoring_active

    try:
        data = request.json
        task_details = {
            'participantId': data.get('participantId'),
            'batch': data.get('batch'),
            'category': data.get('category'),
            'taskDescription': data.get('taskDescription'),
            'name': data.get('name'),
            'estimatedTime': data.get('estimatedTime'),
            'systemType': data.get('systemType', 'system2'),
            'timestamp': datetime.now().isoformat(),
            'startTime': data.get('startTime')
        }

        os.makedirs('./details', exist_ok=True)
        participant_id = data.get('participantId', 'unknown')
        details_file = f'./details/{participant_id}_task_details.json'

        existing_data = []
        if os.path.exists(details_file):
            try:
                with open(details_file, 'r') as f:
                    content = json.load(f)
                    existing_data = content if isinstance(content, list) else [content]
            except Exception:
                existing_data = []

        is_new_file = len(existing_data) == 0
        existing_data.append(task_details)

        with open(details_file, 'w') as f:
            json.dump(existing_data, f, indent=2)

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
                    'message': f'Task details saved but failed to start interventions: {error}',
                    'interventionsStarted': False,
                    'isNewFile': is_new_file,
                    'totalEntries': len(existing_data),
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
        return jsonify({'status': 'error', 'message': f'Failed to save task details: {str(e)}'}), 500


@app.route('/api/stop-interventions', methods=['POST'])
def stop_interventions():
    try:
        success, message = stop_interventions_process()
        return jsonify({
            'status': 'success' if success else 'warning',
            'message': message,
            'platform': platform.system()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error stopping interventions: {str(e)}'}), 500


@app.route('/api/save-feedback', methods=['POST'])
def save_feedback():
    try:
        data = request.json
        participant_id = data.get('participantId')
        if not participant_id:
            return jsonify({'status': 'error', 'message': 'Participant ID is required'}), 400

        feedback_dir = './feedback'
        os.makedirs(feedback_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{participant_id}_feedback_{timestamp}.json"
        data['serverTimestamp'] = datetime.now().isoformat()

        with open(os.path.join(feedback_dir, filename), 'w') as f:
            json.dump(data, f, indent=2)

        return jsonify({'status': 'success', 'message': 'Feedback saved successfully', 'filename': filename})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to save feedback: {str(e)}'}), 500


@app.route('/api/save-assessment', methods=['POST'])
def save_assessment():
    try:
        data = request.json
        participant_id = data.get('participantId')
        if not participant_id:
            return jsonify({'status': 'error', 'message': 'Participant ID is required'}), 400

        details_dir = './details'
        os.makedirs(details_dir, exist_ok=True)
        filename = f"{participant_id}_task_assessment.json"
        filepath = os.path.join(details_dir, filename)

        existing_data = []
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    existing_content = json.load(f)
                    existing_data = existing_content if isinstance(existing_content, list) else [existing_content]
            except Exception:
                existing_data = []

        is_new_file = len(existing_data) == 0
        data['timestamp'] = datetime.now().isoformat()
        existing_data.append(data)

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
    global monitoring_process, monitoring_active

    if monitoring_active and monitoring_process:
        if monitoring_process.poll() is not None:
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
    print(f"Starting Cross-Platform API server on http://localhost:5002")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    app.run(debug=False, use_reloader=False, port=5002, host='0.0.0.0')