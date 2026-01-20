# ILGC Workplace and Distraction Monitor

A comprehensive distraction detection and intervention system for workplace research.

## Quick Install (Recommended)

No programming experience required! Download the installer for your operating system and run.

### Download

| Platform | Download | Requirements |
|----------|----------|--------------|
| Windows | [Download Installer](https://github.com/youruser/ilgc/releases/latest/download/ILGC-Setup-Windows.exe) | Windows 10+ |
| macOS | [Download DMG](https://github.com/youruser/ilgc/releases/latest/download/ILGC-Workplace.dmg) | macOS 10.15+ |

[View all releases](https://github.com/youruser/ilgc/releases)

### Installation Steps

**Windows:**
1. Download ILGC-Setup-Windows.exe
2. Double-click to run the installer
3. Follow the setup wizard
4. Launch from the Start Menu or Desktop

**macOS:**
1. Download ILGC-Workplace.dmg
2. Open the DMG file
3. Drag the app to your Applications folder
4. Launch from Applications

### First Run

1. Grant Camera Permission when prompted
2. Grant Notification Permission (macOS)
3. Connect Heart Rate Monitor (optional)
4. Fill Out Form with participant details
5. Click Start Task to begin

---

## For Developers

### Prerequisites

- Python 3.8 or higher
- Node.js 18+ and npm
- Camera permissions enabled
- Git (for cloning)

### Windows Setup

```bash
cd windows
python -m venv .ilgc
.ilgc\Scripts\activate
pip install -r requirements.txt
```

Start 4 terminals with venv activated:
- Terminal 1: `python api_server.py`
- Terminal 2: `python src/watch.py`
- Terminal 3: `python src/client.py`
- Terminal 4: `python src/collate_data.py`

Start frontend:
```bash
cd frontend
npm install
npm run dev
```

### macOS Setup

```bash
cd mac
python3 -m venv .ilgc
source .ilgc/bin/activate
pip install -r requirements.txt
cp -r lib/pylsl/* .ilgc/lib/python3.13/site-packages/pylsl/lib
```

Start 4 terminals with venv activated:
- Terminal 1: `python api_server.py`
- Terminal 2: `python src/watch.py`
- Terminal 3: `python src/client.py`
- Terminal 4: `python src/collate_data.py`

Start frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## Building from Source

### macOS
```bash
chmod +x build.sh
./build.sh
```

### Windows
```cmd
build.bat
```

---

## How it Works

1. Fill out the task form with participant details
2. Click Start Task to begin monitoring
3. System monitors for distractions via screen content and HRV
4. Interventions are delivered via notifications

## API Endpoints

- POST /api/save-task-details - Save task details and start interventions
- POST /api/stop-interventions - Stop interventions
- POST /api/save-feedback - Save user feedback
- POST /api/save-assessment - Save task assessment
- GET /api/status - Get monitoring status
- GET /api/health - Health check

## Troubleshooting

**Camera Not Working:**
- Windows: Settings > Privacy > Camera > Enable
- macOS: System Preferences > Privacy > Camera

**Notifications Not Appearing (macOS):**
- System Preferences > Notifications > Script Editor > Allow

**Heart Rate Monitor Not Connecting:**
- Ensure Bluetooth is enabled
- Make sure hBand device is powered on

## License

MIT License
