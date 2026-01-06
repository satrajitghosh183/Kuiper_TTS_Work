// Kuiper TTS - Electron Preload Script
// Exposes safe APIs to the renderer process

const { contextBridge, ipcRenderer } = require('electron')

// Expose protected methods to the renderer
contextBridge.exposeInMainWorld('electron', {
  // API
  getApiPort: () => ipcRenderer.invoke('get-api-port'),
  
  // File system
  getAppPath: (name) => ipcRenderer.invoke('get-app-path', name),
  openFolder: (path) => ipcRenderer.invoke('open-folder', path),
  showItemInFolder: (path) => ipcRenderer.invoke('show-item-in-folder', path),
  
  // Platform info
  platform: process.platform,
  
  // Window controls (for custom title bar)
  windowControls: {
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),
  },
})

// Log when preload script loads
console.log('Preload script loaded')

