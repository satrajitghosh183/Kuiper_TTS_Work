import { create } from 'zustand'
import type { SystemCheck, AudioDevice, TrainingStatus, RecordingProgress } from '../lib/api'

interface AppState {
  // System
  systemCheck: SystemCheck | null
  isSystemChecking: boolean

  // Audio
  devices: AudioDevice[]
  selectedDeviceId: number | null
  recommendedGain: number

  // Recording
  recordings: RecordingProgress[]
  currentScriptIndex: number
  currentLineIndex: number
  isRecording: boolean

  // Training
  trainingStatus: TrainingStatus | null
  isTrainingConnected: boolean

  // Actions
  setSystemCheck: (check: SystemCheck | null) => void
  setIsSystemChecking: (checking: boolean) => void
  setDevices: (devices: AudioDevice[]) => void
  setSelectedDeviceId: (id: number | null) => void
  setRecommendedGain: (gain: number) => void
  setRecordings: (recordings: RecordingProgress[]) => void
  setCurrentIndices: (scriptIndex: number, lineIndex: number) => void
  setIsRecording: (recording: boolean) => void
  setTrainingStatus: (status: TrainingStatus | null) => void
  setIsTrainingConnected: (connected: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  systemCheck: null,
  isSystemChecking: false,
  devices: [],
  selectedDeviceId: null,
  recommendedGain: 1.0,
  recordings: [],
  currentScriptIndex: 0,
  currentLineIndex: 0,
  isRecording: false,
  trainingStatus: null,
  isTrainingConnected: false,

  // Actions
  setSystemCheck: (check) => set({ systemCheck: check }),
  setIsSystemChecking: (checking) => set({ isSystemChecking: checking }),
  setDevices: (devices) => set({ devices }),
  setSelectedDeviceId: (id) => set({ selectedDeviceId: id }),
  setRecommendedGain: (gain) => set({ recommendedGain: gain }),
  setRecordings: (recordings) => set({ recordings }),
  setCurrentIndices: (scriptIndex, lineIndex) =>
    set({ currentScriptIndex: scriptIndex, currentLineIndex: lineIndex }),
  setIsRecording: (recording) => set({ isRecording: recording }),
  setTrainingStatus: (status) => set({ trainingStatus: status }),
  setIsTrainingConnected: (connected) => set({ isTrainingConnected: connected }),
}))

