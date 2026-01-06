// Type definitions for Electron preload APIs

export interface ElectronAPI {
  // API port
  getApiPort: () => Promise<number>
  
  // File system
  getAppPath: (name: 'home' | 'appData' | 'userData' | 'temp' | 'desktop' | 'documents' | 'downloads') => Promise<string>
  openFolder: (path: string) => Promise<void>
  showItemInFolder: (path: string) => Promise<void>
  
  // Platform info
  platform: 'darwin' | 'win32' | 'linux'
  
  // Window controls
  windowControls: {
    minimize: () => void
    maximize: () => void
    close: () => void
  }
}

declare global {
  interface Window {
    electron?: ElectronAPI
  }
}

export {}

