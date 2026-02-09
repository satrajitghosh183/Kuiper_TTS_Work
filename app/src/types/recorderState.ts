import { Recording, Script } from '../lib/api'

export interface RecordingSessionState {
  // Current position
  currentScriptIndex: number
  currentLineIndex: number
  
  // Recording state
  recorderState: 'idle' | 'recording' | 'draft' | 'saved'
  isRecording: boolean
  duration: number
  
  // Draft recording
  draftBlob?: {
    recordingKey: string
    blob: Blob
    timestamp: number
  }
  
  // User preferences
  autoSkipRecorded: boolean
  autoStartNext: boolean
  silenceThreshold: number
  silenceDurationMs: number
  maxDurationMs: number
  
  // Metadata
  lastSaved: number
  version: string
}

export interface PersistedState {
  session: RecordingSessionState
  recordings: Array<[string, Recording]>
  scripts: Script[]
  timestamp: number
}
