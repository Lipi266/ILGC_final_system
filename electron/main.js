const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn, execSync } = require('child_process');

const IS_MAC = process.platform === 'darwin';
const IS_WIN = process.platform === 'win32';

let loadingWindow = null;
let mainWindow = null;
let debugWindow = null;
let runningProcesses = [];

const PROJECT_ROOT = app.isPackaged
  ? path.join(process.resourcesPath, 'project')
  : path.join(__dirname, '..');

const SCRIPTS = {
  mac: path.join(PROJECT_ROOT, 'start_mac.sh'),
  win: path.join(PROJECT_ROOT, 'start_windows.bat'),
  stopWin: path.join(PROJECT_ROOT, 'stop_windows.bat'),
};

const FRONTEND_URL = 'http://localhost:8080';
const API_URL      = 'http://localhost:5000/api/health'; // Windows
const API_URL_MAC  = 'http://localhost:5002/api/health'; // Mac

const APP_DATA_DIR = IS_MAC
  ? path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data')
  : path.join(process.env.APPDATA || '', 'ILGC Research', 'data');

const SERVICE_LOG_DIR = path.join(APP_DATA_DIR, 'logs', 'services');

const PID_FILE = IS_MAC ? path.join(APP_DATA_DIR, 'ilgc_pids.txt') : null;

const LOG_FILES = {
  api_server:   path.join(SERVICE_LOG_DIR, 'api_server.log'),
  watch:        path.join(SERVICE_LOG_DIR, 'watch.log'),
  client:       path.join(SERVICE_LOG_DIR, 'client.log'),
  collate_data: path.join(SERVICE_LOG_DIR, 'collate_data.log'),
  run_activity: path.join(SERVICE_LOG_DIR, 'run_activity.log'),
  frontend:     path.join(SERVICE_LOG_DIR, 'frontend.log'),
};

// ── Loading window ─────────────────────────────────────────────
function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width: 520,
    height: 420,
    resizable: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
  });
  loadingWindow.loadFile(path.join(__dirname, 'loading.html'));
}

// ── Main window ───────────────────────────────────────────────
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    show: false,
    titleBarStyle: IS_MAC ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(FRONTEND_URL);

  mainWindow.once('ready-to-show', () => {
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      loadingWindow.close();
      loadingWindow = null;
    }
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    stopAllServices();
  });
}

// ── Debug window ──────────────────────────────────────────────
function createDebugWindow() {
  if (debugWindow && !debugWindow.isDestroyed()) {
    debugWindow.focus();
    return;
  }
  debugWindow = new BrowserWindow({
    width: 900,
    height: 600,
    title: 'ILGC Debug Logs',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
  });
  debugWindow.loadFile(path.join(__dirname, 'debug.html'));
  debugWindow.on('closed', () => { debugWindow = null; });
}

// ── Status messages ────────────────────────────────────────────
function sendStatus(message, progress) {
  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.webContents.send('status', { message, progress });
  }
  console.log(`[status ${progress ?? '?'}%] ${message}`);
}

// ── Poll until URL responds ────────────────────────────────────
function waitForURL(url, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const interval = setInterval(() => {
      http.get(url, (res) => {
        if (res.statusCode < 500) {
          clearInterval(interval);
          resolve();
        }
      }).on('error', () => {
        if (Date.now() - start > timeoutMs) {
          clearInterval(interval);
          reject(new Error(`Timed out waiting for ${url}`));
        }
      });
    }, 1500);
  });
}

// ── Parse calibration progress from a script output line ──────
// Returns a number 0-100 representing how far through the 60s
// calibration window we are, or null if the line is not a calib line.
function parseCalibrationProgress(line) {
  // "Calibrating smartwatch — 45s remaining, keep watch on your wrist…"
  const remaining = line.match(/(\d+)s remaining/);
  if (remaining) {
    const sLeft = parseInt(remaining[1], 10);
    const total = 60;
    const pct = Math.round(((total - sLeft) / total) * 35); // maps 0-60s → 5-40%
    return Math.max(5, Math.min(40, pct + 5));
  }
  // "Calibrating smartwatch — finalising baseline…"
  if (/finalising baseline/i.test(line)) return 42;
  return null;
}

// ── Run the startup script ─────────────────────────────────────
function runStartScript() {
  return new Promise((resolve, reject) => {
    let proc;
    let resolved = false;

    if (IS_MAC) {
      try { fs.chmodSync(SCRIPTS.mac, '755'); } catch (_) {}
      proc = spawn('bash', [SCRIPTS.mac], {
        cwd: PROJECT_ROOT,
        detached: false,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env, TERM: 'xterm' },
      });
    } else if (IS_WIN) {
      proc = spawn('cmd.exe', ['/c', SCRIPTS.win], {
        cwd: PROJECT_ROOT,
        detached: false,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      });
    } else {
      return reject(new Error('Unsupported platform'));
    }

    runningProcesses.push(proc);

    proc.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter(Boolean);
      lines.forEach((line) => {
        const clean = line.replace(/\x1b\[[0-9;]*m/g, '').trim();
        if (!clean) return;
        console.log(`[script] ${clean}`);

        // Calibration progress lines — show with specific progress %
        const calibPct = parseCalibrationProgress(clean);
        if (calibPct !== null) {
          sendStatus(
            clean.replace(/^Calibrating smartwatch — /, '⌚ Calibrating smartwatch — '),
            calibPct
          );
          return;
        }

        // Camera permission warning
        if (/camera permission|Camera.*not.*accessible/i.test(clean)) {
          sendStatus('⚠ Camera permission missing — grant in System Settings > Privacy > Camera', null);
          return;
        }

        // Watch timeout warning (non-blocking)
        if (/calibration timed out/i.test(clean)) {
          sendStatus('⚠ Smartwatch not detected — continuing without HRV features', null);
          return;
        }

        // Calibration complete
        if (/calibration complete/i.test(clean)) {
          sendStatus('⌚ Smartwatch calibrated', 45);
          return;
        }

        // API ready
        if (/api server ready/i.test(clean)) {
          sendStatus('Backend API ready…', 65);
          return;
        }

        // "All services running" — the script signals completion
        if (!resolved && clean.includes('All services running')) {
          resolved = true;
          resolve();
          return;
        }

        // Generic status update (no progress change)
        sendStatus(clean, null);
      });
    });

    proc.stderr.on('data', (data) => {
      const clean = data.toString().replace(/\x1b\[[0-9;]*m/g, '').trim();
      if (clean) {
        console.warn(`[script stderr] ${clean}`);
        if (!clean.includes('setsid') && !clean.includes('WARNING')) {
          sendStatus(`⚠ ${clean}`, null);
        }
      }
    });

    proc.on('error', (err) => {
      if (!resolved) reject(err);
    });

    proc.on('exit', (code) => {
      if (!resolved && code !== 0) {
        reject(new Error(`Startup script exited with code ${code}`));
      }
    });
  });
}

// ── Kill everything on quit ────────────────────────────────────
function stopAllServices() {
  console.log('[cleanup] Stopping all services...');

  try {
    const apiURL = IS_MAC ? 'http://localhost:5002' : 'http://localhost:5000';
    http.get(`${apiURL}/api/stop-interventions`, () => {}).on('error', () => {});
  } catch (_) {}

  if (IS_MAC && PID_FILE && fs.existsSync(PID_FILE)) {
    try {
      const pids = fs.readFileSync(PID_FILE, 'utf8')
        .split('\n').map(s => s.trim()).filter(Boolean);
      for (const pid of pids) {
        try { execSync(`kill -TERM -- -${pid} 2>/dev/null || kill -TERM ${pid} 2>/dev/null || true`); } catch (_) {}
      }
      setTimeout(() => {
        for (const pid of pids) {
          try { execSync(`kill -KILL -- -${pid} 2>/dev/null || kill -KILL ${pid} 2>/dev/null || true`); } catch (_) {}
        }
      }, 2000);
    } catch (_) {}
  }

  if (IS_MAC) {
    const scripts = ['api_server.py', 'watch.py', 'client.py', 'collate_data.py',
                     'run_activity.py', 'interventions.py'];
    for (const s of scripts) {
      try { execSync(`pkill -f "${s}" 2>/dev/null || true`); } catch (_) {}
    }
    try { execSync(`pkill -f "aw-qt" 2>/dev/null; pkill -f "aw-server" 2>/dev/null; pkill -f "aw-watcher" 2>/dev/null || true`); } catch (_) {}
  }

  for (const proc of runningProcesses) {
    try { proc.kill('SIGTERM'); } catch (_) {}
  }
  runningProcesses = [];

  if (IS_WIN && fs.existsSync(SCRIPTS.stopWin)) {
    try {
      execSync(`cmd.exe /c "${SCRIPTS.stopWin}"`, { windowsHide: true, timeout: 10000 });
    } catch (_) {}
  }

  console.log('[cleanup] Done.');
}

function readLogTail(filePath, lines = 200) {
  try {
    if (!fs.existsSync(filePath)) return `(log file not found: ${filePath})`;
    const content = fs.readFileSync(filePath, 'utf8');
    return content.split('\n').slice(-lines).join('\n');
  } catch (e) {
    return `(error reading log: ${e.message})`;
  }
}

// ── App lifecycle ──────────────────────────────────────────────
app.whenReady().then(async () => {
  createLoadingWindow();

  try {
    sendStatus('Starting ILGC services…', 5);

    // The startup script now handles calibration BEFORE starting the API.
    // We wait for the "All services running" signal from the script, which
    // means: calibration done, API up, frontend up.
    //
    // Timeout: calibration takes up to 120s + 30s API start + 30s frontend = 180s.
    // We give 300s (5 min) total to be safe for slow first-run installs.
    sendStatus('Starting smartwatch calibration…', 8);
    const scriptPromise = runStartScript();

    // Wait for the script to emit "All services running".
    // The script itself surfaces calibration progress via stdout,
    // so the user sees live updates in the loading screen.
    await scriptPromise;

    sendStatus('Backend ready — loading frontend…', 80);

    // By the time "All services running" is emitted the frontend Vite
    // server is already starting, but may need a few more seconds.
    await waitForURL(FRONTEND_URL, 30000);

    sendStatus('Almost there…', 95);
    await new Promise((r) => setTimeout(r, 600));

    sendStatus('Done!', 100);
    createMainWindow();

  } catch (err) {
    sendStatus(`Error: ${err.message}`, null);
    console.error('Startup failed:', err);
  }
});

app.on('window-all-closed', () => {
  stopAllServices();
  if (!IS_MAC) app.quit();
});

app.on('activate', () => {
  if (mainWindow === null && loadingWindow === null) createLoadingWindow();
});

app.on('before-quit', () => stopAllServices());

// ── IPC handlers ──────────────────────────────────────────────
ipcMain.on('quit-app', () => {
  stopAllServices();
  app.quit();
});

ipcMain.on('open-external', (_, url) => shell.openExternal(url));
ipcMain.on('open-debug', () => createDebugWindow());

ipcMain.handle('get-log-names', () => Object.keys(LOG_FILES));

ipcMain.handle('get-log', (_, name) => {
  const filePath = LOG_FILES[name];
  if (!filePath) return `Unknown log: ${name}`;
  return readLogTail(filePath, 200);
});

ipcMain.handle('get-health', async () => {
  const apiURL = IS_MAC ? API_URL_MAC : API_URL;
  return new Promise((resolve) => {
    http.get(apiURL, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try { resolve({ ok: true, data: JSON.parse(body) }); }
        catch { resolve({ ok: true, data: body }); }
      });
    }).on('error', (e) => resolve({ ok: false, error: e.message }));
  });
});