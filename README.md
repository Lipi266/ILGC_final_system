# ILGC Workplace and Distraction

## Prerequisites

- Python 3.8 or higher  
- Node.js and npm  
- Camera permissions enabled    

## Setup Instructions

### Windows

1. **Create virtual environment:**
   ```bash
   cd windows
   python3 -m venv .ilgc
   source .ilgc/Scripts/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Grant camera permissions:**
   * Settings > Privacy & Security > Camera
   * Enable camera access for your terminal/command prompt

4. **Start backend services (open 4 terminals, all with venv activated):**
   ```bash
   # Terminal 1
   python3 api_server.py

   # Terminal 2
   cd src
   python3 watch.py

   # Terminal 3
   cd src
   python3 client.py

   # Terminal 4
   cd src
   python3 collate_data.py
   ```

5. **Start frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Open in browser:** Go to the URL shown by Vite (usually `http://localhost:8080/ilgcresearch/`).

### Mac

1. **Create virtual environment:**
   ```bash
   cd Mac
   python3 -m venv .ilgc
   source .ilgc/bin/activate
   ```

2. **Install dependencies & configure pylsl:**
   ```bash
   pip install -r requirements.txt
   cp -r lib/pylsl/* .ilgc/lib/python3.13/site-packages/pylsl/lib
   ```

3. **Grant permissions:**
   * **Camera:** System Preferences > Security & Privacy > Camera
   * **Notifications (for interventions):** Test with:
   ```bash
   osascript -e 'display notification "Keep up the good work!" with title "ILGC Research"'
   ```

4. **Start backend services (open 4 terminals, all with venv activated):**
   ```bash
   # Terminal 1
   python3 api_server.py

   # Terminal 2
   cd src
   python3 watch.py

   # Terminal 3
   cd src
   python3 client.py

   # Terminal 4
   cd src
   python3 collate_data.py
   ```

5. **Start frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Open in browser:** Go to the URL shown by Vite (usually `http://localhost:8080/ilgcresearch/`).


## How it Works

1. Fill out the task form with participant details
2. Click "Start Task" - this will:
   - Save participant ID, batch, task category, and task description to `./details/task_details.json`
   - Start the interventions.py script automatically
   - The interventions script will load the task details and include them in the GPT analysis prompt

The system will now monitor for distractions based on the specific task you've defined!


## API Endpoints

* `POST /api/save-task-details` → Save task details & start interventions
* `POST /api/stop-interventions` → Stop interventions
* `GET /api/status` → Get monitoring status
* `GET /api/get-task-details` → Get current task details



## Troubleshooting

**Mac – Interventions:**
* Allow Script Editor in Notifications settings 
* Ensure `/usr/bin/osascript` has Accessibility settings (Privacy & Security) permissions

