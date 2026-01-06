// Kuiper TTS - Electron Main Process
const { app, BrowserWindow, ipcMain, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const net = require('net')

// Keep a global reference of the window object
let mainWindow = null
let pythonProcess = null
let apiPort = 8765 // Default port - matches run_server.py

// Check if running in development
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

// Find an available port
async function findAvailablePort(startPort) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.listen(startPort, () => {
      const port = server.address().port
      server.close(() => resolve(port))
    })
    server.on('error', () => {
      resolve(findAvailablePort(startPort + 1))
    })
  })
}

// Start the Python backend
async function startPythonBackend() {
  apiPort = await findAvailablePort(8765)
  
  const pythonPath = isDev 
    ? 'python3' 
    : path.join(process.resourcesPath, 'python', 'python')
  
  const backendPath = isDev
    ? path.join(__dirname, '..', '..', 'backend', 'api', 'main.py')
    : path.join(process.resourcesPath, 'backend', 'api', 'main.py')

  console.log(`Starting Python backend on port ${apiPort}...`)
  console.log(`Python path: ${pythonPath}`)
  console.log(`Backend path: ${backendPath}`)

  pythonProcess = spawn(pythonPath, [
    '-u', // Unbuffered output
    '-m', 'uvicorn',
    'backend.api.main:app',
    '--host', '127.0.0.1',
    '--port', apiPort.toString(),
  ], {
    cwd: isDev ? path.join(__dirname, '..', '..') : process.resourcesPath,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`)
  })

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python] ${data.toString().trim()}`)
  })

  pythonProcess.on('error', (error) => {
    console.error('Failed to start Python backend:', error)
  })

  pythonProcess.on('close', (code) => {
    console.log(`Python backend exited with code ${code}`)
    pythonProcess = null
  })

  // Wait for the server to be ready
  await waitForServer(apiPort)
  console.log('Python backend is ready')
}

// Wait for the server to respond
async function waitForServer(port, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/health`)
      if (response.ok) {
        return true
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  throw new Error('Backend server failed to start')
}

// Stop the Python backend
function stopPythonBackend() {
  if (pythonProcess) {
    console.log('Stopping Python backend...')
    pythonProcess.kill('SIGTERM')
    pythonProcess = null
  }
}

// Create the main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: '#101214',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
    show: false, // Don't show until ready
  })

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// App lifecycle
app.whenReady().then(async () => {
  try {
    await startPythonBackend()
    createWindow()
  } catch (error) {
    console.error('Failed to start application:', error)
    app.quit()
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('will-quit', () => {
  stopPythonBackend()
})

// IPC Handlers
ipcMain.handle('get-api-port', () => {
  return apiPort
})

ipcMain.handle('get-app-path', (event, name) => {
  return app.getPath(name)
})

ipcMain.handle('open-folder', async (event, folderPath) => {
  shell.openPath(folderPath)
})

ipcMain.handle('show-item-in-folder', async (event, itemPath) => {
  shell.showItemInFolder(itemPath)
})

