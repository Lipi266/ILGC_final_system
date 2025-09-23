# Setup Instructions

## Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install frontend dependencies:

```bash
cd frontend
npm install
```

## Running the Application

1. Start the Flask API server (in the root directory):

```bash
python api_server.py
```

2. Start the React frontend (in a new terminal):

```bash
cd frontend
npm run dev
```

3. Open your browser and go to the URL shown by Vite (usually http://localhost:8080/ilgcresearch/)

## How it Works

1. Fill out the task form with participant details
2. Click "Start Task" - this will:
   - Save participant ID, batch, task category, and task description to `./details/task_details.json`
   - Start the interventions.py script automatically
   - The interventions script will load the task details and include them in the GPT analysis prompt

The system will now monitor for distractions based on the specific task you've defined!

## API Endpoints

- `POST /api/save-task-details` - Save task details and start interventions
- `POST /api/stop-interventions` - Stop the interventions process
- `GET /api/status` - Get current monitoring status
- `GET /api/get-task-details` - Get current task details
