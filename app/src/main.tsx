import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import { initializeApiPort } from './lib/api'
import './styles/globals.css'

// Initialize API port from Electron before rendering
async function bootstrap() {
  try {
    await initializeApiPort()
  } catch (error) {
    console.warn('Failed to initialize API port:', error)
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>,
  )
}

bootstrap()

