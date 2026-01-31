// API client for Kuiper TTS backend

// Default port - will be overridden by Electron's dynamic port
let apiPort = 8765

// Get the API base URL
function getApiBase(): string {
  return `http://127.0.0.1:${apiPort}/api`
}

// Get the server base URL (without /api)
export function getServerBase(): string {
  return `http://127.0.0.1:${apiPort}`
}

// Set API port (called from Electron preload)
export function setApiPort(port: number): void {
  apiPort = port
  console.log(`API port set to ${port}`)
}

// Initialize port from Electron if available
export async function initializeApiPort(): Promise<void> {
  if (typeof window !== 'undefined' && window.electron?.getApiPort) {
    try {
      const port = await window.electron.getApiPort()
      if (port) {
        setApiPort(port)
      }
    } catch (error) {
      console.warn('Failed to get API port from Electron, using default:', error)
    }
  }
}

// Get current WebSocket URL
export function getWebSocketUrl(): string {
  return `ws://127.0.0.1:${apiPort}/api`
}

interface FetchOptions {
  method?: string
  headers?: Record<string, string>
  body?: object | FormData
}

// Custom error class for API errors
export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message)
    this.name = 'APIError'
  }
}

async function fetchAPI<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { body, ...rest } = options

  const config: RequestInit = {
    ...rest,
    headers: {
      ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...rest.headers,
    },
  }

  if (body) {
    config.body = body instanceof FormData ? body : JSON.stringify(body)
  }

  try {
    const response = await fetch(`${getApiBase()}${endpoint}`, config)

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new APIError(
        error.detail || `HTTP ${response.status}`,
        response.status,
        error.detail
      )
    }

    return response.json()
  } catch (error) {
    if (error instanceof APIError) {
      throw error
    }
    // Network error or other fetch failure
    throw new APIError(
      error instanceof Error ? error.message : 'Network error',
      0,
      'Could not connect to the server. Make sure the backend is running.'
    )
  }
}

// System endpoints
export interface SystemCheck {
  can_train: boolean
  training_backend: string
  gpu_name: string | null
  gpu_vram_gb: number | null
  ram_total_gb: number
  ram_available_gb: number
  storage_free_gb: number
  python_version: string
  cuda_available: boolean
  mps_available: boolean
  warnings: string[]
  errors: string[]
}

export interface TrainingEstimate {
  estimated_time: string
  recommended_batch_size: number
  recommended_epochs: number
}

// Script endpoints
export interface Script {
  name: string
  path: string
  lines: string[]
  line_count: number
}

export const api = {
  // System
  async systemCheck(): Promise<SystemCheck> {
    return fetchAPI('/system/check')
  },

  async trainingEstimate(sampleCount: number): Promise<TrainingEstimate> {
    return fetchAPI('/system/estimate', {
      method: 'POST',
      body: { sample_count: sampleCount },
    })
  },

  // Scripts
  async listScripts(directory?: string): Promise<Script[]> {
    const params = new URLSearchParams()
    if (directory) params.append('directory', directory)
    const query = params.toString()
    return fetchAPI(`/scripts${query ? `?${query}` : ''}`)
  },

  async getScript(scriptName: string): Promise<Script> {
    return fetchAPI(`/scripts/${encodeURIComponent(scriptName)}`)
  },

  // Audio
  async listDevices(): Promise<AudioDevice[]> {
    return fetchAPI('/audio/devices')
  },

  async testDevice(deviceId?: number, duration = 2.0): Promise<AudioTestResult> {
    return fetchAPI('/audio/test', {
      method: 'POST',
      body: { device_id: deviceId, duration_seconds: duration },
    })
  },

  async saveRecording(audioBlob: Blob, filename: string, gain = 1.0): Promise<SaveRecordingResult> {
    const formData = new FormData()
    formData.append('audio_file', audioBlob, filename)
    formData.append('filename', filename)
    formData.append('gain', gain.toString())

    return fetchAPI('/recording/save', {
      method: 'POST',
      body: formData,
    })
  },

  async listRecordings(): Promise<Recording[]> {
    return fetchAPI('/recording/list')
  },

  async getRecordingProgress(): Promise<RecordingProgress[]> {
    return fetchAPI('/recording/progress')
  },

  // Training
  async scanTrainingData(recordingsDir?: string, projectRoot?: string): Promise<ScanTrainingDataResult> {
    const params = new URLSearchParams()
    if (recordingsDir) params.append('recordings_dir', recordingsDir)
    if (projectRoot) params.append('project_root', projectRoot)
    const query = params.toString()
    return fetchAPI(`/training/scan${query ? `?${query}` : ''}`)
  },

  async prepareTraining(config: PrepareTrainingConfig): Promise<PrepareTrainingResult> {
    return fetchAPI('/training/prepare', {
      method: 'POST',
      body: config,
    })
  },

  async startTraining(config: StartTrainingConfig): Promise<{ success: boolean; message: string }> {
    return fetchAPI('/training/start', {
      method: 'POST',
      body: config,
    })
  },

  async getTrainingStatus(): Promise<TrainingStatus> {
    return fetchAPI('/training/status')
  },

  async pauseTraining(): Promise<{ success: boolean; message: string }> {
    return fetchAPI('/training/pause', { method: 'POST' })
  },

  async stopTraining(): Promise<{ success: boolean; message: string }> {
    return fetchAPI('/training/stop', { method: 'POST' })
  },

  // Voice
  async synthesize(text: string, modelPath?: string): Promise<SynthesizeResult> {
    return fetchAPI('/voice/synthesize', {
      method: 'POST',
      body: { text, model_path: modelPath },
    })
  },

  async exportVoice(config: ExportVoiceConfig): Promise<ExportVoiceResult> {
    return fetchAPI('/voice/export', {
      method: 'POST',
      body: config,
    })
  },

  // Health
  async health(): Promise<{ status: string; version: string; training_active: boolean }> {
    return fetchAPI('/health')
  },

  // Check if server is available
  async isServerAvailable(): Promise<boolean> {
    try {
      await this.health()
      return true
    } catch {
      return false
    }
  },
}

// Types
export interface AudioDevice {
  device_id: number
  name: string
  channels: number
  sample_rate: number
  is_default: boolean
}

export interface AudioTestResult {
  success: boolean
  peak_level: number
  rms_level: number
  db_level: number
  is_clipping: boolean
  recommended_gain: number
  error: string | null
}

export interface SaveRecordingResult {
  success: boolean
  path: string
  duration_seconds: number
  peak_amplitude: number
  rms_level: number
  error: string | null
}

export interface Recording {
  filename: string
  text: string
  duration_seconds: number
  is_valid: boolean
  error: string | null
}

export interface RecordingProgress {
  script_name: string
  recorded: number
  total: number
  remaining: number
  percent: number
}

export interface ScanTrainingDataResult {
  recordings_dir: string
  recordings_dir_exists: boolean
  recordings_count: number
  text_files: Array<{
    path: string
    name: string
    line_count: number
  }>
  recordings: Array<{
    filename: string
    path: string
    script_name: string
    index: number
    text: string
    has_text: boolean
  }>
  warnings: string[]
}

export interface PrepareTrainingConfig {
  recordings_dir: string
  output_dir: string
  voice_name?: string
  script_files?: string[]
}

export interface PrepareTrainingResult {
  success: boolean
  total_recordings: number
  valid_recordings: number
  invalid_recordings: number
  total_duration_seconds: number
  metadata_path: string
  audio_dir: string
  errors: string[]
  warnings: string[]
}

export interface StartTrainingConfig {
  metadata_path: string
  audio_dir: string
  output_dir: string
  voice_name?: string
  espeak_voice?: string
  batch_size?: number
  max_epochs?: number
  pretrained_checkpoint?: string
}

export interface TrainingStatus {
  status: 'idle' | 'preparing' | 'training' | 'paused' | 'completed' | 'failed' | 'cancelled'
  epoch: number
  total_epochs: number
  loss: number
  val_loss: number | null
  percent_complete: number
  elapsed_seconds: number
  estimated_remaining_seconds: number
  message: string
}

export interface SynthesizeResult {
  success: boolean
  audio_path: string | null
  duration_seconds: number
  error: string | null
}

export interface ExportVoiceConfig {
  checkpoint_path: string
  output_path: string
  voice_name: string
}

export interface ExportVoiceResult {
  success: boolean
  onnx_path: string
  message: string
}

// WebSocket connection for training updates
export function createTrainingWebSocket(
  onMessage: (status: TrainingStatus) => void,
  onError?: (error: Event) => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(`${getWebSocketUrl()}/training/stream`)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'ping') {
        // Respond to ping
        ws.send('ping')
      } else if (data.type !== 'pong') {
        onMessage(data)
      }
    } catch {
      console.error('Failed to parse training update')
    }
  }

  ws.onerror = (error) => {
    console.error('Training WebSocket error:', error)
    onError?.(error)
  }

  ws.onclose = () => {
    console.log('Training WebSocket closed')
    onClose?.()
  }

  return ws
}

// Helper to format duration
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.round((seconds % 3600) / 60)
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
}
