const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ilgc', {
  // Loading window status updates
  onStatus: (callback) => ipcRenderer.on('status', (_, data) => callback(data)),

  // Quit the app
  quit: () => ipcRenderer.send('quit-app'),

  // Open external URL in system browser
  openExternal: (url) => ipcRenderer.send('open-external', url),

  // Debug panel: list available log files
  getLogNames: () => ipcRenderer.invoke('get-log-names'),

  // Debug panel: get tail of a log file by name
  getLog: (name) => ipcRenderer.invoke('get-log', name),

  // Debug panel: hit the API health endpoint
  getHealth: () => ipcRenderer.invoke('get-health'),
});