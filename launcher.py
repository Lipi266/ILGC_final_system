#!/usr/bin/env python3
"""
ILGC Workplace Monitor - Unified Launcher
==========================================
This script manages all backend services and serves the frontend.

When run as a bundled app, it imports and runs services in threads.
When run as a script, it can use subprocess for better isolation.
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
import importlib.util

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MACOS = SYSTEM == "Darwin"
IS_FROZEN = getattr(sys, 'frozen', False)

# Base directory
if IS_FROZEN:
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(os.path.dirname(sys.executable))
    if IS_WINDOWS:
        OS_DIR = BASE_DIR / "windows"
    else:
        OS_DIR = BASE_DIR / "mac"
else:
    BASE_DIR = Path(__file__).parent.resolve()
    APP_DIR = BASE_DIR
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

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Setup logging to both file and console."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
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
    """Check camera permission."""
    logger.info("Checking camera permissions...")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.release()
            logger.info("Camera permission granted")
            return True
        else:
            logger.warning("Camera access denied or not available")
            return False
    except Exception as e:
        logger.warning(f"Could not check camera: {e}")
        return True

# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

class ServiceRunner:
    """Runs backend services - uses threads when frozen, subprocesses when not."""
    
    def __init__(self):
        self.threads = {}
        self.processes = {}
        self.running = False
        self.frontend_server = None
        self.frontend_thread = None
        self.stop_event = threading.Event()
    
    def _run_script_as_module(self, name, script_path):
        """Import and run a Python script as a module in a thread."""
        logger.info(f"Loading {name} from {script_path}")
        
        try:
            # Change to the OS directory so relative paths work
            original_cwd = os.getcwd()
            os.chdir(OS_DIR)
            
            # Add paths to sys.path
            src_dir = OS_DIR / "src"
            if str(OS_DIR) not in sys.path:
                sys.path.insert(0, str(OS_DIR))
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            # Load and execute the module
            spec = importlib.util.spec_from_file_location(name, script_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                
                logger.info(f"Executing {name}...")
                spec.loader.exec_module(module)
            else:
                logger.error(f"Could not load spec for {script_path}")
                
        except Exception as e:
            logger.error(f"Error running {name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            os.chdir(original_cwd)
    
    def _run_script_as_subprocess(self, name, script_path):
        """Run a Python script as a subprocess."""
        logger.info(f"Starting subprocess for {name}")
        
        try:
            env = os.environ.copy()
            
            if IS_MACOS:
                pylsl_lib = OS_DIR / "lib" / "pylsl"
                if pylsl_lib.exists():
                    env['DYLD_LIBRARY_PATH'] = f"{pylsl_lib}:{env.get('DYLD_LIBRARY_PATH', '')}"
            
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(OS_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env
            )
            
            self.processes[name] = process
            
            # Read output
            for line in iter(process.stdout.readline, b''):
                if line and self.running:
                    logger.info(f"[{name}] {line.decode('utf-8', errors='replace').rstrip()}")
                if not self.running:
                    break
                    
        except Exception as e:
            logger.error(f"Error in subprocess {name}: {e}")
    
    def start_service(self, name, script_path):
        """Start a service in a thread."""
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return False
        
        if IS_FROZEN:
            # When frozen, run as module in thread
            thread = threading.Thread(
                target=self._run_script_as_module,
                args=(name, script_path),
                name=f"service-{name}",
                daemon=True
            )
        else:
            # When running as script, use subprocess
            thread = threading.Thread(
                target=self._run_script_as_subprocess,
                args=(name, script_path),
                name=f"service-{name}",
                daemon=True
            )
        
        thread.start()
        self.threads[name] = thread
        logger.info(f"Started {name}")
        return True
    
    def start_frontend(self):
        """Start the frontend HTTP server."""
        logger.info(f"Starting frontend server on port {FRONTEND_PORT}...")
        
        if not FRONTEND_DIST_DIR.exists():
            logger.error(f"Frontend dist not found at {FRONTEND_DIST_DIR}")
            logger.error("Please build the frontend first: cd mac/frontend && npm run build")
            return False
        
        try:
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
    
    def start_all(self):
        """Start all services."""
        self.running = True
        self.stop_event.clear()
        
        # Create necessary directories
        for dir_name in ['details', 'feedback', 'collated', 'interventions', 'screenshot', 'watch']:
            (OS_DIR / dir_name).mkdir(parents=True, exist_ok=True)
        
        # Start backend services
        # Note: Start api_server first, then others with delays
        services_to_start = [
            ("api_server", BACKEND_SCRIPTS["api_server"]),
            ("collate_data", BACKEND_SCRIPTS["collate_data"]),
            ("client", BACKEND_SCRIPTS["client"]),
            # Note: watch.py requires user interaction for calibration, start last or skip
        ]
        
        for name, path in services_to_start:
            if self.start_service(name, path):
                time.sleep(1)  # Stagger startup
        
        # Start frontend
        self.start_frontend()
        
        return True
    
    def stop_all(self):
        """Stop all services."""
        logger.info("Stopping all services...")
        self.running = False
        self.stop_event.set()
        
        # Stop frontend
        if self.frontend_server:
            self.frontend_server.shutdown()
        
        # Stop subprocesses if any
        for name, proc in self.processes.items():
            if proc.poll() is None:
                logger.info(f"Stopping {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except:
                    proc.kill()
        
        logger.info("All services stopped")


class FrontendHandler(SimpleHTTPRequestHandler):
    """HTTP handler for serving the frontend."""
    
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)
    
    def log_message(self, format, *args):
        logger.debug(f"HTTP: {args[0]}")
    
    def do_GET(self):
        path = self.path.split('?')[0]
        file_path = Path(self.directory) / path.lstrip('/')
        
        if not file_path.exists() and not path.startswith('/api'):
            self.path = '/index.html'
        
        return super().do_GET()
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


# ============================================================================
# MAIN
# ============================================================================

def open_browser(delay=5):
    """Open browser after delay."""
    time.sleep(delay)
    url = f"http://localhost:{FRONTEND_PORT}"
    logger.info(f"Opening browser at {url}")
    webbrowser.open(url)


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("   ILGC Workplace & Distraction Monitor v1.0.0")
    print("=" * 60)
    print(f"\nPlatform: {SYSTEM}")
    print(f"Mode: {'Bundled App' if IS_FROZEN else 'Development'}")
    print(f"Working directory: {OS_DIR}")
    
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Frozen: {IS_FROZEN}")
    logger.info(f"OS directory: {OS_DIR}")
    logger.info(f"Frontend: {FRONTEND_DIST_DIR}")
    
    # Check if OS directory exists
    if not OS_DIR.exists():
        print(f"\nERROR: Directory not found: {OS_DIR}")
        logger.error(f"OS directory not found: {OS_DIR}")
        if not IS_FROZEN:
            input("Press Enter to exit...")
        return 1
    
    # Check camera
    print("\nChecking permissions...")
    check_camera_permission()
    
    # Create service runner
    print("\nStarting services...")
    runner = ServiceRunner()
    
    # Signal handler
    def signal_handler(signum, frame):
        logger.info("Shutdown signal received")
        runner.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start services
    if not runner.start_all():
        print("\nERROR: Failed to start services")
        logger.error("Failed to start services")
        if not IS_FROZEN:
            input("Press Enter to exit...")
        return 1
    
    # Status
    print("\n" + "-" * 40)
    print("Services started!")
    print(f"Frontend: http://localhost:{FRONTEND_PORT}")
    print("-" * 40)
    print("\nOpening browser in 5 seconds...")
    print("Press Ctrl+C to stop\n")
    
    # Open browser
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Keep running
    try:
        while runner.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        runner.stop_all()
    
    print("Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
