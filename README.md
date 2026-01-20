# ILGC Workplace and Distraction Monitor

A comprehensive distraction detection and intervention system for workplace research.

## Quick Install (Recommended)

No programming experience required! Download the installer for your operating system.

### Download Latest Version

| Platform | Download | Requirements |
|----------|----------|--------------|
| **Windows** | [ILGC-Setup-Windows.exe](../../releases/latest/download/ILGC-Setup-Windows.exe) | Windows 10+ |
| **macOS** | [ILGC-Workplace.dmg](../../releases/latest/download/ILGC-Workplace.dmg) | macOS 10.15+ |

> **[View All Releases](../../releases)** - Download previous versions or standalone executables

### Installation

**Windows:**
1. Download `ILGC-Setup-Windows.exe` from the link above
2. Double-click to run the installer
3. Follow the setup wizard
4. Launch from Start Menu or Desktop shortcut

**macOS:**
1. Download `ILGC-Workplace.dmg` from the link above
2. Double-click the DMG file to open it
3. Drag the ILGC app to the Applications folder (shortcut shown in DMG)
4. Open from Applications folder
5. If blocked by Gatekeeper: Right-click the app > Open > Open

### First Run

1. **Grant Camera Permission** when prompted
2. **Connect Heart Rate Monitor** (optional) - Turn on your hBand
3. **Fill Out the Form** with participant details
4. **Click Start Task** to begin monitoring

---

## For Developers

### Prerequisites

- Python 3.8+
- Node.js 18+ and npm
- Git

### Quick Start (Run from Source)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/ILGC_final_system.git
cd ILGC_final_system

# Run the unified launcher (starts all services)
python launcher.py
```

Or manually start each service:

**macOS:**
```bash
cd mac
python3 -m venv .ilgc && source .ilgc/bin/activate
pip install -r requirements.txt
cp -r lib/pylsl/* .ilgc/lib/python3.*/site-packages/pylsl/lib

# Start services in separate terminals:
python api_server.py
python src/watch.py
python src/client.py
python src/collate_data.py

# Start frontend:
cd frontend && npm install && npm run dev
```

**Windows:**
```cmd
cd windows
python -m venv .ilgc && .ilgc\Scripts\activate
pip install -r requirements.txt

# Start services in separate terminals:
python api_server.py
python src/watch.py
python src/client.py
python src/collate_data.py

# Start frontend:
cd frontend && npm install && npm run dev
```

---

## Building Installers

### Build Locally

**macOS:**
```bash
chmod +x build.sh
./build.sh
# Output: dist/ILGC-Workplace.dmg
```

**Windows:**
```cmd
build.bat
# Output: dist/ILGC-Workplace.exe and Output/ILGC-Setup-Windows.exe
```

### Creating a Release (Automatic via GitHub Actions)

1. **Tag a new version:**
   ```bash
   git add .
   git commit -m "Release v1.0.0"
   git tag v1.0.0
   git push origin main --tags
   ```

2. **GitHub Actions automatically:**
   - Builds for Windows and macOS
   - Creates installers
   - Publishes to GitHub Releases

3. **Download links auto-update** to point to the latest release

### Manual Release Upload

If you build locally and want to upload manually:

1. Go to your repo > **Releases** > **Create a new release**
2. Create a new tag (e.g., `v1.0.0`)
3. Upload your build files:
   - `ILGC-Workplace.dmg` (macOS)
   - `ILGC-Setup-Windows.exe` (Windows installer)
   - `ILGC-Workplace.exe` (Windows standalone)
4. Publish the release

**Important:** Do NOT push large executable files to git. Use GitHub Releases for distribution.

---

## How it Works

1. Fill out the task form with participant details
2. Click Start Task to begin monitoring
3. System monitors distractions via screen content and HRV data
4. Interventions delivered as notifications when distraction detected

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/save-task-details` | POST | Save task and start interventions |
| `/api/stop-interventions` | POST | Stop monitoring |
| `/api/status` | GET | Get monitoring status |
| `/api/health` | GET | Health check |

## Troubleshooting

**Camera Not Working:**
- macOS: System Preferences > Privacy & Security > Camera > Allow
- Windows: Settings > Privacy > Camera > Enable

**App Won't Open (macOS):**
- Right-click the app > Open > Open (bypasses Gatekeeper)

**Heart Rate Monitor Not Connecting:**
- Ensure Bluetooth is enabled
- Make sure hBand is powered on and not connected to another device

## License

MIT License
