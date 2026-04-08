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

// PID file written by start_mac.sh so we can kill all grandchildren
const PID_FILE = IS_MAC
  ? path.join(
      process.env.HOME,
      'Library', 'Application Support', 'ILGC Research',
      'data', 'ilgc_pids.txt'
    )
  : null;

// Log files written by start_mac.sh
const LOG_FILES = IS_MAC ? {
  api_server:    path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data', 'logs', 'services', 'api_server.log'),
  watch:         path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data', 'logs', 'services', 'watch.log'),
  client:        path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data', 'logs', 'services', 'client.log'),
  collate_data:  path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data', 'logs', 'services', 'collate_data.log'),
  run_activity:  path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data', 'logs', 'services', 'run_activity.log'),
  frontend:      path.join(process.env.HOME, 'Library', 'Application Support', 'ILGC Research', 'data', 'logs', 'services', 'frontend.log'),
} : {};

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

        // Surface camera warning to the loading UI without blocking startup
        if (clean.includes('camera permission') || clean.includes('Camera') || clean.includes('CAMERA')) {
          sendStatus('⚠ Camera permission missing — grant in System Settings > Privacy > Camera', null);
        } else {
          sendStatus(clean, null);
        }

        if (!resolved && clean.includes('All services running')) {
          resolved = true;
          resolve();
        }
      });
    });

    proc.stderr.on('data', (data) => {
      const clean = data.toString().replace(/\x1b\[[0-9;]*m/g, '').trim();
      if (clean) {
        console.warn(`[script stderr] ${clean}`);
        // Don't surface every stderr line — only meaningful warnings
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

  // 1. Ask the API to stop interventions cleanly first
  try {
    const apiURL = IS_MAC ? 'http://localhost:5002' : 'http://localhost:5000';
    http.get(`${apiURL}/api/stop-interventions`, () => {}).on('error', () => {});
  } catch (_) {}

  // 2. Kill processes tracked by PID file (includes grandchildren like interventions.py)
  if (IS_MAC && PID_FILE && fs.existsSync(PID_FILE)) {
    try {
      const pids = fs.readFileSync(PID_FILE, 'utf8')
        .split('\n')
        .map(s => s.trim())
        .filter(Boolean);
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

  // 3. Kill by script name to catch any stragglers
  if (IS_MAC) {
    const scripts = ['api_server.py', 'watch.py', 'client.py', 'collate_data.py',
                     'run_activity.py', 'interventions.py'];
    for (const s of scripts) {
      try { execSync(`pkill -f "${s}" 2>/dev/null || true`); } catch (_) {}
    }
    // Also kill ActivityWatch
    try { execSync(`pkill -f "aw-qt" 2>/dev/null; pkill -f "aw-server" 2>/dev/null; pkill -f "aw-watcher" 2>/dev/null || true`); } catch (_) {}
  }

  // 4. Kill tracked Node child processes
  for (const proc of runningProcesses) {
    try { proc.kill('SIGTERM'); } catch (_) {}
  }
  runningProcesses = [];

  // 5. Windows stop script
  if (IS_WIN && fs.existsSync(SCRIPTS.stopWin)) {
    try {
      execSync(`cmd.exe /c "${SCRIPTS.stopWin}"`, { windowsHide: true, timeout: 10000 });
    } catch (_) {}
  }

  console.log('[cleanup] Done.');
}

// ── Read last N lines from a log file ─────────────────────────
function readLogTail(filePath, lines = 200) {
  try {
    if (!fs.existsSync(filePath)) return `(log file not found: ${filePath})`;
    const content = fs.readFileSync(filePath, 'utf8');
    const all = content.split('\n');
    return all.slice(-lines).join('\n');
  } catch (e) {
    return `(error reading log: ${e.message})`;
  }
}

// ── App lifecycle ──────────────────────────────────────────────
app.whenReady().then(async () => {
  createLoadingWindow();

  try {
    sendStatus('Starting ILGC services…', 5);
    sendStatus('Launching backend services…', 15);
    const scriptPromise = runStartScript();

    sendStatus('Waiting for backend API…', 40);
    const apiURL = IS_MAC ? API_URL_MAC : API_URL;

    await Promise.race([
      scriptPromise.catch(() => {}),
      waitForURL(apiURL, 90000),
    ]);

    sendStatus('Backend ready — waiting for frontend…', 70);
    await waitForURL(FRONTEND_URL, 60000);

    sendStatus('Almost there…', 90);
    await new Promise((r) => setTimeout(r, 800));

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