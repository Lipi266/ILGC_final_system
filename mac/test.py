import subprocess

def send_notification(title, message):
    """Send a macOS notification via AppleScript."""
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}"'
    ])

if __name__ == "__main__":
    send_notification("Test", "If you see this, notifications are working!")
        