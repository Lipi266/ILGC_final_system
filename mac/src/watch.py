#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime

# For Windows GUI thread handling - moved to top of file
import platform
if platform.system() == 'Windows':
    # Set the event loop policy for Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    from asyncio.windows_events import ProactorEventLoop
    # Force use of ProactorEventLoop for BLE operations
    if sys.version_info >= (3, 8):
        asyncio.set_event_loop(ProactorEventLoop())

import numpy as np
from bleak import BleakClient, BleakScanner
from pylsl import StreamInfo, StreamOutlet

# ——— PARAMETERS ————————————————————————————————————————
BASELINE_DURATION = 60.0  # seconds
WINDOW_DURATION = 30.0  # seconds

OUTPUT_DIR = "./watch"
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
METRICS_DIR = os.path.join(OUTPUT_DIR, "metrics")
LOG_FILE = os.path.join(OUTPUT_DIR, "hrv_processor.log")

# Path for storing the JSON data file
WATCH_DATA_FILE = os.path.join(OUTPUT_DIR, "watch_data.json")
BASELINE_FILE = os.path.join(OUTPUT_DIR, "baseline_calibration.json")

HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
TARGET_DEVICE_NAME = "hBand"

# ——— LOGGING SETUP —————————————————————————————————————
# Create directories first
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(METRICS_DIR, exist_ok=True)

# ---Configure logging-----------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger("hrv_processor")


# ——— MAIN PROCESSOR CLASS —————————————————————————————————
class HRVProcessor:
    """
    Connects to MAX-HEALTH-BAND, computes baseline + windowed HRV metrics,
    detects stress → distraction (3 windows in a row), streams and saves JSON.
    """

    def __init__(self):
        # Data buffers
        self.heart_rate_values = deque()
        self.rr_intervals_values = deque()
        self.raw_hr_data = []

        # LSL stream: 4 channels (HR, SDNN, RMSSD, pNN50)
        self.stream_info = StreamInfo(
            "HRV_CognitiveLoad", "HRV", 4, 1, "float32", "hrvuid12345"
        )
        self.lsl_outlet = StreamOutlet(self.stream_info)

        # State
        self.session_start_time = None
        self.baseline_start_time = None
        self.current_window_start = None
        self.baseline_metrics = {}
        self.baseline_complete = False
        self.ble_client = None

        # Stress/distraction tracking
        self.stress_count = 0
        
        # JSON data tracking - always start with sequence 1
        self.current_sequence = 0
        self.reset_json_file()
        
        # Try to load existing baseline
        self.load_baseline_from_file()
        
        # Monitoring control
        self.monitoring_mode = False
        self.monitoring_start_time = None
        self.data_points_collected = 0
        # Remove the limit on data points
        self.continuous_monitoring = True

    def reset_json_file(self):
        """Reset the JSON file with an empty structure for a new session"""
        data = {
            "entries": [],
            "current_sequence": 0
        }
        with open(WATCH_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Reset watch data file at {WATCH_DATA_FILE}")

    def initialize_json_file(self):
        """Initialize the JSON file with an empty structure if it doesn't exist"""
        # This method is kept for compatibility but now just calls reset_json_file
        self.reset_json_file()

    def save_to_json(self, data_entry):
        """Save a new entry to the JSON file"""
        try:
            # Load existing data
            with open(WATCH_DATA_FILE, 'r') as f:
                file_data = json.load(f)
            
            # Update sequence number
            self.current_sequence += 1
            data_entry["sequence_number"] = self.current_sequence
            
            # Add new entry
            file_data["entries"].append(data_entry)
            file_data["current_sequence"] = self.current_sequence
            
            # Write back to file
            with open(WATCH_DATA_FILE, 'w') as f:
                json.dump(file_data, f, indent=2)
                
            logger.info(f"Saved entry #{self.current_sequence} to watch data file")
            return True
        except Exception as e:
            logger.error(f"Error saving to watch data file: {e}")
            return False

    async def initialize_device(self):
        logger.info(f"Scanning for BLE devices matching '{TARGET_DEVICE_NAME}'...")
        
        # Add retries for device scanning
        max_scan_attempts = 3
        for attempt in range(1, max_scan_attempts + 1):
            try:
                logger.info(f"Scan attempt {attempt}/{max_scan_attempts}...")
                devices = await BleakScanner.discover()
                
                # Log all discovered devices for debugging
                logger.info(f"Found {len(devices)} Bluetooth devices:")
                for i, d in enumerate(devices):
                    dev_name = d.name if d.name else "Unknown"
                    logger.info(f"  {i+1}. {dev_name} ({d.address})")
                
                # Look for our target device
                target = None
                for d in devices:
                    # Compare device name case-insensitively
                    if d.name and TARGET_DEVICE_NAME.lower() in d.name.lower():
                        target = d
                        break

                if target is not None:
                    break
                    
                if attempt < max_scan_attempts:
                    logger.info(f"Target device not found, retrying in 2 seconds...")
                    await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error during BLE scan attempt {attempt}: {e}")
                if attempt < max_scan_attempts:
                    logger.info(f"Retrying scan in 2 seconds...")
                    await asyncio.sleep(2)

        if target is None:
            logger.error(f"Device '{TARGET_DEVICE_NAME}' not found after {max_scan_attempts} attempts. Make sure it's on and advertising.")
            return False

        logger.info(f"Found target device: {target.name} ({target.address})")

        try:
            # Connect to device with retry logic
            max_connect_attempts = 2
            for attempt in range(1, max_connect_attempts + 1):
                try:
                    logger.info(f"Connection attempt {attempt}/{max_connect_attempts}...")
                    self.ble_client = BleakClient(target)
                    await self.ble_client.connect()

                    if not self.ble_client.is_connected:
                        logger.error("Failed to connect - client reports not connected")
                        if attempt < max_connect_attempts:
                            logger.info("Retrying connection in 2 seconds...")
                            await asyncio.sleep(2)
                            continue
                        else:
                            return False

                    logger.info("Connected to device successfully.")

                    # Subscribe to Heart Rate notifications
                    await self.ble_client.start_notify(
                        HEART_RATE_UUID, self.hr_notification_handler
                    )
                    logger.info(f"Subscribed to HR notifications (UUID: {HEART_RATE_UUID}).")

                    return True
                    
                except Exception as e:
                    logger.error(f"Connection attempt {attempt} failed: {e}")
                    if attempt < max_connect_attempts:
                        logger.info("Retrying connection in 2 seconds...")
                        await asyncio.sleep(2)
                    else:
                        raise

            return False

        except Exception as e:
            logger.error(f"Error connecting to device: {e}")
            if self.ble_client and self.ble_client.is_connected:
                try:
                    await self.ble_client.disconnect()
                except:
                    pass
            return False

    async def hr_notification_handler(self, sender, data):
        """Called on each incoming HR notification from the band."""
        decoded = self.decode_heart_rate(data.hex())
        heart_rate = decoded["Heart Rate (BPM)"]
        rr_intervals = decoded.get("RR Intervals (ms)", [])
        timestamp = time.time()

        # Mark session & baseline start on first sample
        if self.session_start_time is None:
            self.session_start_time = timestamp
            self.baseline_start_time = timestamp
            self.current_window_start = timestamp
            logger.info(f"Session start at {datetime.fromtimestamp(timestamp)}")

        # Buffer samples
        self.heart_rate_values.append((timestamp, heart_rate))
        for rr in rr_intervals:
            # convert ms to seconds
            self.rr_intervals_values.append((timestamp, rr / 1000.0))
        self.raw_hr_data.append(
            {
                "timestamp": timestamp,
                "heart_rate": heart_rate,
                "rr_intervals": rr_intervals,
            }
        )

        # Baseline collection (calibration)
        if (
            not self.baseline_complete
            and timestamp - self.baseline_start_time >= BASELINE_DURATION
        ):
            self.compute_baseline_metrics()
            self.baseline_complete = True
            self.current_window_start = timestamp
            logger.info("Baseline calibration complete.")
            
            # After baseline is complete, we don't automatically start monitoring

        # Monitoring mode - collect data continuously
        elif (
            self.baseline_complete 
            and self.monitoring_mode
            and timestamp - self.current_window_start >= WINDOW_DURATION
        ):
            self.process_window(self.current_window_start, timestamp)
            self.current_window_start = timestamp

    def decode_heart_rate(self, hex_string):
        """
        Decodes the Heart Rate Measurement characteristic (UUID 0x2A37) from a BLE device.

        Args:
            hex_string: Raw heart rate measurement data in hexadecimal format.

        Returns:
            dict: Decoded values (Heart Rate, Sensor Contact, Energy Expended, RR Intervals).
        """
        data = bytes.fromhex(hex_string)
        if len(data) < 2:
            return {"error": "Invalid data length"}

        flags = data[0]
        # Bit 0: 0 => UINT8, 1 => UINT16 for heart rate value
        hr_format_uint16 = flags & 0x01
        # Bits 1-2: Sensor contact status
        sensor_contact = (flags >> 1) & 0x03
        # # Bit 3: Energy Expended field present
        # energy_expended_present = (flags >> 3) & 0x01
        # Bit 4: RR-Interval field present
        rr_intervals_present = (flags >> 4) & 0x01

        index = 1
        if hr_format_uint16:
            heart_rate = int.from_bytes(data[index : index + 2], byteorder="little")
            index += 2
        else:
            heart_rate = data[index]
            index += 1

        # energy_expended = None
        # if energy_expended_present and len(data) >= index + 2:
        #     energy_expended = int.from_bytes(data[index:index+2], byteorder='little')
        #     index += 2

        rr_intervals = []
        while rr_intervals_present and index + 1 < len(data):
            rr_intervals.append(
                int.from_bytes(data[index : index + 2], byteorder="little")
            )
            index += 2

        return {"Heart Rate (BPM)": heart_rate, "RR Intervals (ms)": rr_intervals}

    def calculate_mean_hr(self, window):
        now = time.time()
        vals = [hr for t, hr in self.heart_rate_values if now - t <= window]
        return float(np.mean(vals)) if vals else None

    def compute_sdnn_window(self, window):
        now = time.time()
        vals = [rr for t, rr in self.rr_intervals_values if now - t <= window]
        return float(np.std(vals) * 1000) if len(vals) > 1 else None

    def compute_rmssd_window(self, window):
        now = time.time()
        vals = [rr for t, rr in self.rr_intervals_values if now - t <= window]
        if len(vals) < 2:
            return None
        return float(np.sqrt(np.mean(np.diff(vals) ** 2)) * 1000)

    def compute_pnn_window(self, window, thresh=50):
        now = time.time()
        vals = [rr for t, rr in self.rr_intervals_values if now - t <= window]
        if len(vals) < 2:
            return None
        diffs = np.abs(np.diff(vals)) * 1000
        return float(100 * np.sum(diffs > thresh) / len(diffs))

    def compute_baseline_metrics(self):
        """Compute and LSL-stream the baseline HRV metrics."""
        logger.info("Computing baseline metrics...")
        baseline_hr = self.calculate_mean_hr(BASELINE_DURATION)
        baseline_sdnn = self.compute_sdnn_window(BASELINE_DURATION)
        baseline_rmssd = self.compute_rmssd_window(BASELINE_DURATION)
        baseline_pnn50 = self.compute_pnn_window(BASELINE_DURATION, 50)

        self.baseline_metrics = {
            "hr": baseline_hr if baseline_hr is not None else 0,
            "sdnn": baseline_sdnn if baseline_sdnn is not None else 0,
            "rmssd": baseline_rmssd if baseline_rmssd is not None else 0,
            "pnn50": baseline_pnn50 if baseline_pnn50 is not None else 0,
        }
        b = self.baseline_metrics
        logger.info(
            f"Baseline metrics: HR={b['hr']:.1f}, "
            f"SDNN={b['sdnn']:.1f}, RMSSD={b['rmssd']:.1f}, "
            f"pNN50={b['pnn50']:.1f}%"
        )

        # stream baseline
        self.lsl_outlet.push_sample([b["hr"], b["sdnn"], b["rmssd"], b["pnn50"]])
        
        # Save baseline to persistent file
        self.save_baseline_to_file()

    def save_baseline_to_file(self):
        """Save baseline metrics to a persistent file"""
        baseline_data = {
            "timestamp": datetime.now().isoformat(),
            "baseline_metrics": self.baseline_metrics,
            "baseline_duration": BASELINE_DURATION,
            "window_duration": WINDOW_DURATION
        }
        try:
            with open(BASELINE_FILE, 'w') as f:
                json.dump(baseline_data, f, indent=2)
            logger.info(f"Baseline calibration saved to {BASELINE_FILE}")
            return True
        except Exception as e:
            logger.error(f"Error saving baseline to file: {e}")
            return False

    def load_baseline_from_file(self):
        """Load baseline metrics from persistent file if it exists"""
        if os.path.exists(BASELINE_FILE):
            try:
                with open(BASELINE_FILE, 'r') as f:
                    baseline_data = json.load(f)
                
                self.baseline_metrics = baseline_data.get("baseline_metrics", {})
                
                # Validate that all required metrics are present
                required_keys = ["hr", "sdnn", "rmssd", "pnn50"]
                if all(key in self.baseline_metrics for key in required_keys):
                    self.baseline_complete = True
                    logger.info("Loaded existing baseline calibration from file")
                    logger.info(f"Baseline loaded from: {baseline_data.get('timestamp', 'unknown time')}")
                    b = self.baseline_metrics
                    logger.info(
                        f"Loaded baseline metrics: HR={b['hr']:.1f}, "
                        f"SDNN={b['sdnn']:.1f}, RMSSD={b['rmssd']:.1f}, "
                        f"pNN50={b['pnn50']:.1f}%"
                    )
                    return True
                else:
                    logger.warning("Incomplete baseline data found, will need to recalibrate")
                    
            except Exception as e:
                logger.error(f"Error loading baseline from file: {e}")
        
        logger.info("No valid baseline calibration found, will need to calibrate")
        return False

    def save_baseline_to_json(self):
        """Save the baseline metrics to the JSON file"""
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        baseline_entry = {
            "timestamp": timestamp_str,
            "watch_data": {
                "is_baseline": True,
                "baseline_metrics": self.baseline_metrics,
                "interpretation": "Baseline measurements established as reference point for stress detection",
                "feedback": "Baseline calibration complete. Reference HRV metrics set."
            }
        }
        self.save_to_json(baseline_entry)
        logger.info("Saved baseline metrics to watch data file")

    def start_monitoring(self):
        """Start the monitoring phase to collect data continuously"""
        if not self.baseline_complete:
            logger.warning("Cannot start monitoring without completing baseline calibration first")
            return False
            
        self.monitoring_mode = True
        self.monitoring_start_time = time.time()
        self.data_points_collected = 0
        self.current_window_start = time.time()
        logger.info("Started monitoring phase - collecting data continuously")
        return True

    def calculate_stress_score(self, changes):
        """
        Calculate a weighted stress score based on multiple HRV metrics.
        Returns a score between 0.0 (no stress) and 1.0 (maximum stress).
        """
        # Apply weights to each normalized metric
        # Current weights: HR (30%), SDNN (25%), RMSSD (25%), pNN50 (20%)
        score = (
            min(1.0, max(0, changes["hr"] / 15)) * 0.3
            + min(1.0, max(0, -changes["sdnn"] / 20)) * 0.25
            + min(1.0, max(0, -changes["rmssd"] / 20)) * 0.25
            + min(1.0, max(0, -changes["pnn50"] / 25)) * 0.2
        )
        return score

    def evaluate_distraction(self, stress_level, changes):
        """
        More sophisticated distraction detection with weighted stress accumulation
        and gradual recovery. Takes into account stress severity.
        """
        # Increase counter based on stress level
        if stress_level == "high":
            self.stress_count += 1.5
        elif stress_level == "mild":
            self.stress_count += 0.7
        else:
            # Gradual recovery from stress when not stressed
            self.stress_count = max(0, self.stress_count - 0.5)

        # Default threshold for distraction
        threshold = 4.0

        # Consider additional factors (optional)
        hr_volatility = abs(changes["hr"])
        if hr_volatility > 20:
            threshold -= 1.0  # Lower threshold if HR is very volatile

        # Return whether distraction threshold is met
        return self.stress_count >= threshold

    def process_window(self, start_time, end_time):
        """Compute windowed HRV, detect stress/distraction, stream & save."""
        window_duration = end_time - start_time

        # Current metrics
        current_hr = self.calculate_mean_hr(window_duration) or 0
        current_sdnn = self.compute_sdnn_window(window_duration) or 0
        current_rmssd = self.compute_rmssd_window(window_duration) or 0
        current_pnn50 = self.compute_pnn_window(window_duration, 50) or 0

        # Percent changes vs baseline
        changes = {}
        for k, cur in (("hr", current_hr), ("sdnn", current_sdnn), ("rmssd", current_rmssd), ("pnn50", current_pnn50),):
            base = self.baseline_metrics.get(k, 1)
            changes[k] = 100 * (cur - base) / base if base else 0

        # Calculate stress score and determine level
        stress_score = self.calculate_stress_score(changes)
        level = (
            "High" if stress_score > 0.7 else ("Mild" if stress_score > 0.4 else "Not Stressed")
        )

        # Evaluate distraction using the new method
        distraction = self.evaluate_distraction(level, changes)

        logger.info(
            f"Window @{end_time-self.session_start_time:.1f}s -> stress={level} "
            f"(score={stress_score:.2f}, streak={self.stress_count:.1f})"
            + ("!!! DISTRACTION !!!" if distraction else "")
        )

        # Stream current HRV
        current_lsl = [
            current_hr if current_hr is not None else 0,
            current_sdnn if current_sdnn is not None else 0,
            current_rmssd if current_rmssd is not None else 0,
            current_pnn50 if current_pnn50 is not None else 0,
        ]
        self.lsl_outlet.push_sample(current_lsl)

        # Save metrics to both the original location and the new JSON file
        rec = {
            "timestamp": end_time,
            "elapsed": end_time - self.session_start_time,
            "duration": window_duration,
            "current": {
                "hr": current_hr,
                "sdnn": current_sdnn,
                "rmssd": current_rmssd,
                "pnn50": current_pnn50,
            },
            "changes": changes,
            "stress_score": stress_score,
            "stress": level,
            "streak": self.stress_count,
            "distraction": distraction,
        }
        fn = os.path.join(METRICS_DIR, f"metrics_{datetime.now():%Y%m%d_%H%M%S}.json")
        with open(fn, "w") as f:
            json.dump(rec, f, indent=2)
            
        # Save to the watch_data.json file
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        watch_data_entry = {
            "timestamp": timestamp_str,
            "watch_data": {
                "is_baseline": False,
                "current_metrics": {
                    "hr": current_hr,
                    "sdnn": current_sdnn,
                    "rmssd": current_rmssd,
                    "pnn50": current_pnn50,
                },
                "changes_from_baseline": changes,
                "stress_score": stress_score,
                "stress_level": level,
                "distraction_detected": distraction,
                "interpretation": self.get_stress_interpretation(level, stress_score, distraction),
                "feedback": self.get_user_feedback(level, stress_score, distraction)
            }
        }
        self.save_to_json(watch_data_entry)

    def get_stress_interpretation(self, level, score, distraction):
        """Generate an interpretation based on stress level and distraction status"""
        if level == "High":
            if distraction:
                return "High stress detected with potential distraction. HRV metrics show significant deviation from baseline."
            else:
                return "High stress detected. HRV metrics show significant deviation from baseline."
        elif level == "Mild":
            return "Mild stress detected. HRV metrics show moderate deviation from baseline."
        else:
            return "Normal stress levels. HRV metrics are close to baseline."
            
    def get_user_feedback(self, level, score, distraction):
        """Generate user feedback based on stress level and distraction status"""
        if distraction:
            return "Consider taking a short break to refocus attention. Distraction detected."
        elif level == "High":
            return "Consider stress reduction techniques like deep breathing."
        elif level == "Mild":
            return "Be mindful of increasing stress levels."
        else:
            return "Current stress levels are within normal range."

    async def start(self):
        return await self.initialize_device()

    async def stop(self):
        logger.info("Stopping…")
        if self.ble_client and self.ble_client.is_connected:
            await self.ble_client.stop_notify(HEART_RATE_UUID)
            await self.ble_client.disconnect()
            logger.info("Disconnected.")


# ——— ENTRY POINT —————————————————————————————————————————
async def main():
    proc = HRVProcessor()
    if not await proc.start():
        print("Failed to connect to the watch. Please make sure your device is turned on and in range.")
        sys.exit(1)

    logger.info("Watch connected successfully.")
    
    # Check if calibration is needed
    if proc.baseline_complete:
        print("\nExisting calibration found!")
        print("==========================")
        print("Using previously saved baseline calibration.")
        b = proc.baseline_metrics
        print(f"Baseline metrics: HR={b['hr']:.1f}, SDNN={b['sdnn']:.1f}, RMSSD={b['rmssd']:.1f}, pNN50={b['pnn50']:.1f}%")
        print("Skipping calibration and proceeding to monitoring.")
        
        # Save the loaded baseline to the current session's JSON
        proc.save_baseline_to_json()
        
    else:
        # Calibration phase
        print("\nCalibration Phase:")
        print("==================")
        print("This will establish a baseline for your heart rate metrics.")
        print("It will take about 60 seconds. Please remain still and relaxed.")
        
        # Wait for user input or automated input from the parent process
        print("Press Enter to start calibration: ", end="", flush=True)
        input()  # This will receive input from either the user or the parent process
        
        # Wait for baseline calibration to complete
        logger.info("Starting baseline calibration...")
        calibration_start = time.time()
        while not proc.baseline_complete:
            if time.time() - calibration_start > 120:  # Safety timeout of 2 minutes
                print("Calibration timeout - please try again.")
                await proc.stop()
                sys.exit(1)
            await asyncio.sleep(1)
            
            # Print progress indicators
            progress = min(100, int((time.time() - calibration_start) / BASELINE_DURATION * 100))
            if progress % 10 == 0:
                print(f"Calibration: {progress}% complete...", end="\r", flush=True)
        
        # Save the baseline metrics to JSON after calibration
        proc.save_baseline_to_json()
        
        print("\nCalibration complete!")
        print("Baseline metrics established and saved for future sessions.")
    
    # Monitoring phase
    print("\nMonitoring Phase:")
    print("=================")
    print("This will collect data continuously.")
    print("Please continue with your normal activities.")
    
    proc.start_monitoring()
    
    # Wait for monitoring to continue indefinitely
    monitoring_start = time.time()
    while proc.monitoring_mode:
        await asyncio.sleep(1)
    
    print("\nMonitoring stopped.")
    print("Data saved to watch_data.json")
    
    # Allow a moment for the parent process to read the output
    await asyncio.sleep(2)
    

if __name__ == "__main__":
    asyncio.run(main())
