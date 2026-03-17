const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ilgc', {
  // Loading window receives status updates from main process
  onStatus: (callback) => ipcRenderer.on('status', (_, data) => callback(data)),
  // Allow the loading/error screen to quit the app
  quit: () => ipcRenderer.send('quit-app'),
  // Open a URL in the system browser (used for feedback form link)
  openExternal: (url) => ipcRenderer.send('open-external', url),
});