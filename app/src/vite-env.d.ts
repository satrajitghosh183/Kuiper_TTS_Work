/// <reference types="vite/client" />

interface Window {
  electron?: {
    getApiPort: () => Promise<number>
    getAppPath: (name: string) => Promise<string>
    openFolder: (path: string) => Promise<void>
    showItemInFolder: (path: string) => Promise<void>
    platform: 'darwin' | 'win32' | 'linux'
    windowControls: {
      minimize: () => void
      maximize: () => void
      close: () => void
    }
  }
}

