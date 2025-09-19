import cv2
import mss
import requests
import base64
import time
import os
import json
from datetime import datetime
import shutil

SERVER_URL = "http://10.1.45.59:8001/caption"

SAVE_DIR = "./screenshot"
CAPTION_FILE = os.path.join(SAVE_DIR, "combined_captions.json")
os.makedirs(SAVE_DIR, exist_ok=True)

# Clear existing screenshots folder
if os.path.exists(SAVE_DIR):
    for file in os.listdir(SAVE_DIR):
        file_path = os.path.join(SAVE_DIR, file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error clearing file {file_path}: {e}")
print("Cleared existing screenshots folder")

# Clear existing captions file
captions_data = {}
with open(CAPTION_FILE, "w") as f:
    json.dump(captions_data, f, indent=2)
print("Cleared existing captions file")


def capture_screenshot():
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[0])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(SAVE_DIR, f"screenshot_{timestamp}.png")
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=img_path)
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64


def capture_webcam():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(SAVE_DIR, f"webcam_{timestamp}.jpg")
    cv2.imwrite(img_path, frame)
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64


def send_images():
    # Capture both images first
    screenshot_b64 = capture_screenshot()
    webcam_b64 = capture_webcam()

    payload = {"screenshot": screenshot_b64, "webcam": webcam_b64}

    try:
        r = requests.post(SERVER_URL, json=payload)
        if r.ok:
            captions = r.json()
            print("[Captions]", captions)
            # Store locally
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            captions_data[timestamp] = captions
            with open(CAPTION_FILE, "w") as f:
                json.dump(captions_data, f, indent=2)
        else:
            print("[Error]", r.text)
    except Exception as e:
        print("[Failed]", e)


if __name__ == "__main__":
    try:
        while True:
            send_images()
            time.sleep(10)  # capture every 10 seconds
    except KeyboardInterrupt:
        print("\nStopped.")

# --------------------------------------------------------------------------------------------------------------
# import requests
# import base64
# import time
# import os
# import json
# from datetime import datetime
# import mss

# # ---- CONFIG ----
# # Replace with your server's IP or domain
# SERVER_URL = "http://10.1.45.59:8001/caption"

# SAVE_DIR = "Screenshots"
# CAPTION_FILE = "captions.json"
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Load existing captions if available
# if os.path.exists(CAPTION_FILE):
#     with open(CAPTION_FILE, "r") as f:
#         captions_data = json.load(f)
# else:
#     captions_data = {}

# # ---- FUNCTIONS ----
# def capture_and_send():
#     with mss.mss() as sct:
#         screenshot = sct.grab(sct.monitors[1])  # capture primary monitor
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         img_path = os.path.join(SAVE_DIR, f"{timestamp}.png")

#         # Save screenshot locally
#         mss.tools.to_png(screenshot.rgb, screenshot.size, output=img_path)

#         # Encode to base64
#         with open(img_path, "rb") as f:
#             b64 = base64.b64encode(f.read()).decode("utf-8")

#         # Send to server
#         try:
#             r = requests.post(SERVER_URL, json={"image": b64})
#             if r.ok:
#                 caption = r.json().get("caption", "No caption")
#                 print(f"[{timestamp}] Caption:", caption)

#                 captions_data[os.path.basename(img_path)] = caption
#                 with open(CAPTION_FILE, "w") as f:
#                     json.dump(captions_data, f, indent=2)
#             else:
#                 print(f"[{timestamp}] Error from server:", r.text)
#         except Exception as e:
#             print(f"[{timestamp}] Failed to connect to server:", e)

# # ---- MAIN LOOP ----
# if __name__ == "__main__":
#     try:
#         while True:
#             capture_and_send()
#             time.sleep(10)  # capture every 10 seconds
#     except KeyboardInterrupt:
#         print("\nStopped.")
#         print("\nStopped.")
