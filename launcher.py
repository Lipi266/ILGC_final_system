#!/usr/bin/env python3
"""
ILGC Workplace Monitor - Unified Launcher
==========================================
This script manages all backend services and serves the frontend for the
ILGC Workplace and Distraction monitoring application.

It handles:
- Starting all 4 Python backend services (api_server, watch, client, collate_data)
- Serving the pre-built frontend static files
- Process monitoring and automatic restart on crash
- Graceful shutdown on Ctrl+C
- Logging to a single log file
- Opening the browser automatically
- Permission checking for camera/notifications
"""

import subprocess
import sys
import os
import time
import signal
import threading
import logging
import webbrowser
import platform
import json
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
import shutil

# ============================================================================
# CONFIGURATION
# ============================================================================

# Detect the OS and set appropriate paths
SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MACOS = SYSTEM == "Darwin"

# Base directory (where the executable or script is located)
if getattr(sys, 'frozen', False):
    # Running as compiled executable (PyInstaller)
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(os.path.dirname(sys.executable))
else:
    # Running as script
    BASE_DIR = Path(__file__).parent.resolve()
    APP_DIR = BASE_DIR

# OS-specific paths
if IS_WINDOWS:
    OS_DIR = APP_DIR / "windows"
else:
    OS_DIR = APP_DIR / "mac"

# Configuration
FRONTEND_PORT = 8080
API_PORT = 5002 if IS_MACOS else 5000
FRONTEND_DIST_DIR = OS_DIR / "frontend" / "dist"
LOGS_DIR = APP_DIR / "logs"
LOG_FILE = LOGS_DIR / "ilgc.log"

# Backend scripts
BACKEND_SCRIPTS = {
    "api_server": OS_DIR / "api_server.py",
    "watch": OS_DIR / "src" / "watch.py",
    "client": OS_DIR / "src" / "client.py",
    "collate_data": OS_DIR / "src" / "collate_data.py",
}

# Process restart configuration
MAX_RESTART_ATTEMPTS = 3
RESTART_COOLDOWN = 5  # seconds

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Setup logging to both file and console."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger("launcher")

logger = setup_logging()

# ============================================================================
# PERMISSION CHECKING
# ============================================================================

def check_camera_permission():
    """Check and request camera permission."""
    logger.info("Checking camera permissions...")
    
    if IS_MACOS:
        try:
            # On macOS, try to access the camera which will trigger permission dialog
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.release()
                logger.info("Camera permission granted")
                return True
            else:
                logger.warning("Camera access denied or not available")
                show_permission_dialog(
                    "Camera Permission Required",
                    "Please grant camera access in System Preferences > Privacy & Security > Camera"
                )
                return False
        except ImportError:
            logger.warning("OpenCV not available, skipping camera check")
            return True
        except Exception as e:
            logger.error(f"Error checking camera permission: {e}")
            return False
    
    elif IS_WINDOWS:
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.release()
                logger.info("Camera permission granted")
                return True
            else:
                logger.warning("Camera access denied or not available")
                show_permission_dialog(
                    "Camera Permission Required",
                    "Please grant camera access in Settings > Privacy > Camera"
                )
                return False
        except ImportError:
            logger.warning("OpenCV not available, skipping camera check")
            return True
        except Exception as e:
            logger.error(f"Error checking camera permission: {e}")
            return False
    
    return True

def check_notification_permission():
    """Check notification permission (macOS only)."""
    if not IS_MACOS:
        return True
    
    logger.info("Checking notification permissions...")
    try:
        # Test notification
        result = subprocess.run(
            ['osascript', '-e', 'display notification "ILGC is starting..." with title "ILGC Workplace Monitor"'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info("Notification permission granted")
            return True
        else:
            logger.warning("Notification permission may not be granted")
            return True  # Don't block on notification permission
    except Exception as e:
        logger.warning(f"Could not test notification permission: {e}")
        return True

def show_permission_dialog(title, message):
    """Show a dialog box with permission instructions."""
    if IS_MACOS:
        try:
            applescript = f'''
display dialog "{message}" with title "{title}" buttons {{"OK"}} default button "OK" with icon caution
'''
            subprocess.run(['osascript', '-e', applescript], capture_output=True)
        except Exception as e:
            logger.error(f"Could not show dialog: {e}")
            print(f"\n⚠️  {title}\n{message}\n")
    
    elif IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x30)
        except Exception as e:
            logger.error(f"Could not show dialog: {e}")
            print(f"\n⚠️  {title}\n{message}\n")
    
    else:
        print(f"\n⚠️  {title}\n{message}\n")

# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

class ProcessManager:
    """Manages all backend processes."""
    
    def __init__(self):
        self.processes = {}
        self.restart_counts = {}
        self.running = False
        self.monitor_thread = None
        self.frontend_server = None
        self.frontend_thread = None
    
    def get_python_executable(self):
        """Get the Python executable path."""
        if getattr(sys, 'frozen', False):
            # Running as compiled - use bundled Python
            return sys.executable
        else:
            # Running as script - use current Python
            return sys.executable
    
    def start_backend_process(self, name, script_path):
        """Start a single backend process."""
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return None
        
        python_exec = self.get_python_executable()
        working_dir = OS_DIR
        
        logger.info(f"Starting {name} from {script_path}")
        
        try:
            # Set up environment
            env = os.environ.copy()
            
            # macOS-specific: Add pylsl library path
            if IS_MACOS:
                pylsl_lib_path = OS_DIR / "lib" / "pylsl"
                if pylsl_lib_path.exists():
                    env['DYLD_LIBRARY_PATH'] = f"{pylsl_lib_path}:{env.get('DYLD_LIBRARY_PATH', '')}"
            
            # Create subprocess
            if IS_WINDOWS:
                # Windows: Use CREATE_NO_WINDOW flag to hide console
                CREATE_NO_WINDOW = 0x08000000
                process = subprocess.Popen(
                    [python_exec, str(script_path)],
                    cwd=str(working_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=CREATE_NO_WINDOW
                )
            else:
                # macOS/Linux
                process = subprocess.Popen(
                    [python_exec, str(script_path)],
                    cwd=str(working_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env
                )
            
            # Start output reader thread
            output_thread = threading.Thread(
                target=self._read_process_output,
                args=(name, process),
                daemon=True
            )
            output_thread.start()
            
            logger.info(f"Started {name} (PID: {process.pid})")
            return process
            
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")
            return None
    
    def _read_process_output(self, name, process):
        """Read and log process output."""
        process_logger = logging.getLogger(f"process.{name}")
        try:
            for line in iter(process.stdout.readline, b''):
                if line:
                    decoded_line = line.decode('utf-8', errors='replace').rstrip()
                    process_logger.info(decoded_line)
        except Exception as e:
            logger.debug(f"Output reader for {name} stopped: {e}")
    
    def start_all_backend(self):
        """Start all backend processes."""
        logger.info("Starting all backend services...")
        
        for name, script_path in BACKEND_SCRIPTS.items():
            process = self.start_backend_process(name, script_path)
            if process:
                self.processes[name] = process
                self.restart_counts[name] = 0
            else:
                logger.error(f"Failed to start {name}")
        
        return len(self.processes) > 0
    
    def start_frontend(self):
        """Start the frontend server."""
        logger.info(f"Starting frontend server on port {FRONTEND_PORT}...")
        
        # Check if frontend dist exists
        if not FRONTEND_DIST_DIR.exists():
            logger.warning(f"Frontend dist directory not found at {FRONTEND_DIST_DIR}")
            logger.info("Attempting to build frontend...")
            if not self._build_frontend():
                logger.error("Could not build frontend. Please run 'npm run build' in the frontend directory.")
                return False
        
        try:
            # Custom handler to serve from dist directory with proper base path
            handler = partial(FrontendHandler, directory=str(FRONTEND_DIST_DIR))
            
            self.frontend_server = HTTPServer(('0.0.0.0', FRONTEND_PORT), handler)
            self.frontend_thread = threading.Thread(
                target=self.frontend_server.serve_forever,
                daemon=True
            )
            self.frontend_thread.start()
            
            logger.info(f"Frontend server started at http://localhost:{FRONTEND_PORT}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start frontend server: {e}")
            return False
    
    def _build_frontend(self):
        """Attempt to build the frontend."""
        frontend_dir = OS_DIR / "frontend"
        
        if not frontend_dir.exists():
            return False
        
        try:
            # Check for npm
            npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
            
            # Install dependencies
            logger.info("Installing frontend dependencies...")
            subprocess.run(
                [npm_cmd, "install"],
                cwd=str(frontend_dir),
                check=True,
                capture_output=True
            )
            
            # Build
            logger.info("Building frontend...")
            subprocess.run(
                [npm_cmd, "run", "build"],
                cwd=str(frontend_dir),
                check=True,
                capture_output=True
            )
            
            return FRONTEND_DIST_DIR.exists()
            
        except Exception as e:
            logger.error(f"Frontend build failed: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor processes and restart if crashed."""
        logger.info("Starting process monitor...")
        
        while self.running:
            for name, process in list(self.processes.items()):
                if process.poll() is not None:
                    # Process has exited
                    exit_code = process.returncode
                    logger.warning(f"{name} exited with code {exit_code}")
                    
                    # Check if we should restart
                    if self.restart_counts[name] < MAX_RESTART_ATTEMPTS:
                        logger.info(f"Restarting {name} (attempt {self.restart_counts[name] + 1}/{MAX_RESTART_ATTEMPTS})")
                        time.sleep(RESTART_COOLDOWN)
                        
                        new_process = self.start_backend_process(name, BACKEND_SCRIPTS[name])
                        if new_process:
                            self.processes[name] = new_process
                            self.restart_counts[name] += 1
                        else:
                            logger.error(f"Failed to restart {name}")
                    else:
                        logger.error(f"{name} exceeded max restart attempts")
            
            time.sleep(2)  # Check every 2 seconds
    
    def start(self):
        """Start all services."""
        self.running = True
        
        # Start backend services
        if not self.start_all_backend():
            logger.error("Failed to start backend services")
            return False
        
        # Start frontend server
        if not self.start_frontend():
            logger.warning("Frontend server not started, but continuing with backend")
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        self.monitor_thread.start()
        
        return True
    
    def stop(self):
        """Stop all services gracefully."""
        logger.info("Stopping all services...")
        self.running = False
        
        # Stop frontend server
        if self.frontend_server:
            logger.info("Stopping frontend server...")
            self.frontend_server.shutdown()
        
        # Stop all backend processes
        for name, process in self.processes.items():
            if process.poll() is None:
                logger.info(f"Stopping {name} (PID: {process.pid})...")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {name}")
                    process.kill()
                    process.wait()
        
        logger.info("All services stopped")
    
    def get_status(self):
        """Get status of all services."""
        status = {
            "backend": {},
            "frontend": self.frontend_server is not None,
            "running": self.running
        }
        
        for name, process in self.processes.items():
            status["backend"][name] = {
                "running": process.poll() is None,
                "pid": process.pid if process.poll() is None else None,
                "restart_count": self.restart_counts.get(name, 0)
            }
        
        return status


class FrontendHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving the frontend."""
    
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)
    
    def log_message(self, format, *args):
        """Log HTTP requests."""
        logger.debug(f"HTTP: {args[0]}")
    
    def do_GET(self):
        """Handle GET requests with SPA support."""
        # Handle SPA routing - serve index.html for unknown paths
        path = self.path.split('?')[0]
        
        # Check if file exists
        file_path = Path(self.directory) / path.lstrip('/')
        
        if not file_path.exists() and not path.startswith('/api'):
            # Serve index.html for SPA routes
            self.path = '/index.html'
        
        return super().do_GET()
    
    def end_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def open_browser(delay=3):
    """Open the browser after a delay."""
    time.sleep(delay)
    url = f"http://localhost:{FRONTEND_PORT}"
    logger.info(f"Opening browser at {url}")
    webbrowser.open(url)

def print_banner():
    """Print application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          ILGC Workplace & Distraction Monitor                 ║
║                                                               ║
║          Version 1.0.0                                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    logger.info("=" * 60)
    logger.info("ILGC Workplace Monitor Starting")
    logger.info("=" * 60)

def print_status(manager):
    """Print current status."""
    status = manager.get_status()
    
    print("\n📊 Service Status:")
    print("-" * 40)
    
    for name, info in status["backend"].items():
        icon = "✅" if info["running"] else "❌"
        pid_info = f" (PID: {info['pid']})" if info["pid"] else ""
        print(f"  {icon} {name}{pid_info}")
    
    frontend_icon = "✅" if status["frontend"] else "❌"
    print(f"  {frontend_icon} frontend (port {FRONTEND_PORT})")
    
    print("-" * 40)
    print(f"\n🌐 Open http://localhost:{FRONTEND_PORT} in your browser")
    print("🛑 Press Ctrl+C to stop all services\n")

def main():
    """Main entry point."""
    print_banner()
    
    # Log system info
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Base directory: {BASE_DIR}")
    logger.info(f"OS directory: {OS_DIR}")
    logger.info(f"Frontend dist: {FRONTEND_DIST_DIR}")
    
    # Check permissions
    logger.info("Checking permissions...")
    camera_ok = check_camera_permission()
    notification_ok = check_notification_permission()
    
    if not camera_ok:
        logger.warning("Camera permission not granted - some features may not work")
    
    # Create process manager
    manager = ProcessManager()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        manager.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if IS_WINDOWS:
        # Windows-specific signal handling
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except AttributeError:
            pass
    
    # Start all services
    if not manager.start():
        logger.error("Failed to start services")
        sys.exit(1)
    
    # Print status
    print_status(manager)
    
    # Open browser in background
    browser_thread = threading.Thread(target=open_browser, args=(3,), daemon=True)
    browser_thread.start()
    
    # Keep running
    try:
        while manager.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        manager.stop()

if __name__ == "__main__":
    main()
