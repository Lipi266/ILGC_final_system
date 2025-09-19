
import subprocess
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if sys.platform.startswith("linux"):
    print(sys.platform)
    script = os.path.join(BASE_DIR, "..", "util", "linux.sh")
    os.chmod(script, 0o755)
    subprocess.run(["bash", script])

elif sys.platform == "darwin":
    print(sys.platform)
    script = os.path.join(BASE_DIR, "..", "util", "mac.sh")
    os.chmod(script, 0o755)
    subprocess.run(["bash", script])

elif sys.platform == "win32":
    print(sys.platform)
    script = os.path.join(BASE_DIR, "..", "util", "windows.bat")
    subprocess.run(["cmd", "/c", script])
