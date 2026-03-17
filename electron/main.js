const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');

const IS_MAC = process.platform === 'darwin';
const IS_WIN = process.platform === 'win32';

let loadingWindow = null;
let mainWindow = null;
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

// ── Loading window ─────────────────────────────────────────────
function createLoadingWindow() {
  loadingWindow = new BrowserWindow({
    width: 480,
    height: 340,
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

// ── Main window (wraps the Vite frontend) ─────────────────────
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

// ── Send status messages to the loading window ─────────────────
function sendStatus(message, progress) {
  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.webContents.send('status', { message, progress });
  }
}

// ── Poll until a URL responds ──────────────────────────────────
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
        // Not ready yet — keep polling
        if (Date.now() - start > timeoutMs) {
          clearInterval(interval);
          reject(new Error(`Timed out waiting for ${url}`));
        }
      });
    }, 1500);
  });
}

// ── Run the platform startup script ───────────────────────────
function runStartScript() {
  return new Promise((resolve, reject) => {
    let proc;

    if (IS_MAC) {
      // Make script executable then run it
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

    // Stream stdout → loading window status messages
    proc.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter(Boolean);
      lines.forEach((line) => {
        // Strip ANSI colour codes
        const clean = line.replace(/\x1b\[[0-9;]*m/g, '').trim();
        if (clean) sendStatus(clean, null);
      });
    });

    proc.stderr.on('data', (data) => {
      const clean = data.toString().replace(/\x1b\[[0-9;]*m/g, '').trim();
      if (clean) sendStatus(`⚠ ${clean}`, null);
    });

    proc.on('error', (err) => reject(err));

    // The script runs indefinitely (it's a service launcher).
    // We resolve as soon as it emits its "all services running" banner.
    proc.stdout.on('data', (data) => {
      if (data.toString().includes('All services running')) {
        resolve();
      }
    });

    // Fallback: if the process exits unexpectedly before we resolved
    proc.on('exit', (code) => {
      if (code !== 0) reject(new Error(`Startup script exited with code ${code}`));
    });
  });
}

// ── Kill everything on quit ────────────────────────────────────
function stopAllServices() {
  if (IS_WIN && fs.existsSync(SCRIPTS.stopWin)) {
    try {
      // Run the stop script synchronously on exit
      const { execSync } = require('child_process');
      execSync(`cmd.exe /c "${SCRIPTS.stopWin}"`, { windowsHide: true, timeout: 10000 });
    } catch (_) {}
  }

  runningProcesses.forEach((proc) => {
    try { proc.kill('SIGTERM'); } catch (_) {}
  });
  runningProcesses = [];
}

// ── App lifecycle ──────────────────────────────────────────────
app.whenReady().then(async () => {
  createLoadingWindow();

  try {
    sendStatus('Starting ILGC services…', 5);

    // Step 1 — run the startup script
    sendStatus('Launching backend services…', 15);
    const scriptPromise = runStartScript();

    // Step 2 — wait for the script to announce readiness OR
    //           fall back to polling the API
    sendStatus('Waiting for backend API…', 40);
    const apiURL = IS_MAC ? API_URL_MAC : API_URL;

    await Promise.race([
      scriptPromise.catch(() => {}),          // may never resolve on its own
      waitForURL(apiURL, 90000),
    ]);

    sendStatus('Backend ready — waiting for frontend…', 70);
    await waitForURL(FRONTEND_URL, 60000);

    sendStatus('Almost there…', 90);
    await new Promise((r) => setTimeout(r, 800)); // brief pause looks polished

    sendStatus('Done!', 100);
    createMainWindow();

  } catch (err) {
    sendStatus(`Error: ${err.message}`, null);
    // Keep the loading window open so the user can read the error.
    // A "Quit" button in loading.html can call window.close().
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