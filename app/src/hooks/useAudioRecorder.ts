import { useState, useRef, useCallback, useEffect } from 'react'

// Convert audio chunks to WAV format
async function convertToWav(chunks: Blob[]): Promise<Blob> {
  const audioBlob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' })
  const arrayBuffer = await audioBlob.arrayBuffer()
  const audioContext = new AudioContext({ sampleRate: 22050 })
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
  
  // Convert to mono if needed
  const samples = audioBuffer.numberOfChannels === 1
    ? audioBuffer.getChannelData(0)
    : audioBuffer.getChannelData(0) // Use first channel for mono
  
  // Convert float32 (-1 to 1) to int16 (-32768 to 32767)
  const int16Samples = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    int16Samples[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
  }
  
  // Create WAV file
  const wavBuffer = new ArrayBuffer(44 + int16Samples.length * 2)
  const view = new DataView(wavBuffer)
  
  // WAV header
  const writeString = (offset: number, string: string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }
  
  writeString(0, 'RIFF')
  view.setUint32(4, 36 + int16Samples.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // audio format (PCM)
  view.setUint16(22, 1, true) // channels (mono)
  view.setUint32(24, 22050, true) // sample rate
  view.setUint32(28, 22050 * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  writeString(36, 'data')
  view.setUint32(40, int16Samples.length * 2, true)
  
  // Write audio data
  const int16View = new Int16Array(wavBuffer, 44)
  int16View.set(int16Samples)
  
  return new Blob([wavBuffer], { type: 'audio/wav' })
}

interface AudioRecorderState {
  isRecording: boolean
  isPaused: boolean
  duration: number
  audioLevel: number
  audioBlob: Blob | null
  error: string | null
}

interface UseAudioRecorderOptions {
  sampleRate?: number
  channelCount?: number
  onDataAvailable?: (blob: Blob) => void
}

export function useAudioRecorder(options: UseAudioRecorderOptions = {}) {
  const { sampleRate = 22050, channelCount = 1, onDataAvailable } = options

  const [state, setState] = useState<AudioRecorderState>({
    isRecording: false,
    isPaused: false,
    duration: 0,
    audioLevel: 0,
    audioBlob: null,
    error: null,
  })

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startTimeRef = useRef<number>(0)
  const animationFrameRef = useRef<number>(0)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording()
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [])

  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current || !state.isRecording) return

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(dataArray)

    // Calculate average level
    const sum = dataArray.reduce((a, b) => a + b, 0)
    const average = sum / dataArray.length
    const normalizedLevel = average / 255

    setState((prev) => ({
      ...prev,
      audioLevel: normalizedLevel,
      duration: (Date.now() - startTimeRef.current) / 1000,
    }))

    animationFrameRef.current = requestAnimationFrame(updateAudioLevel)
  }, [state.isRecording])

  const startRecording = useCallback(
    async (deviceId?: string) => {
      try {
        // Reset state
        chunksRef.current = []
        setState((prev) => ({
          ...prev,
          isRecording: true,
          isPaused: false,
          duration: 0,
          audioBlob: null,
          error: null,
        }))

        // Get media stream
        const constraints: MediaStreamConstraints = {
          audio: {
            sampleRate,
            channelCount,
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
            ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
          },
        }

        const stream = await navigator.mediaDevices.getUserMedia(constraints)
        streamRef.current = stream

        // Set up audio analysis
        audioContextRef.current = new AudioContext({ sampleRate })
        analyserRef.current = audioContextRef.current.createAnalyser()
        analyserRef.current.fftSize = 256

        const source = audioContextRef.current.createMediaStreamSource(stream)
        source.connect(analyserRef.current)

        // Set up media recorder
        const mimeType = MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4'

        mediaRecorderRef.current = new MediaRecorder(stream, { mimeType })

        mediaRecorderRef.current.ondataavailable = (event) => {
          if (event.data.size > 0) {
            chunksRef.current.push(event.data)
          }
        }

        mediaRecorderRef.current.onstop = async () => {
          // Convert WebM/MP4 to WAV using Web Audio API
          const audioBlob = await convertToWav(chunksRef.current)
          setState((prev) => ({ ...prev, audioBlob }))
          onDataAvailable?.(audioBlob)
        }

        // Start recording
        startTimeRef.current = Date.now()
        mediaRecorderRef.current.start(100) // Collect data every 100ms

        // Start level monitoring
        updateAudioLevel()
      } catch (err) {
        const error = err instanceof Error ? err.message : 'Failed to start recording'
        setState((prev) => ({
          ...prev,
          isRecording: false,
          error,
        }))
      }
    },
    [sampleRate, channelCount, onDataAvailable, updateAudioLevel]
  )

  const stopRecording = useCallback(() => {
    // Stop animation frame
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }

    // Stop media recorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }

    // Stop stream tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close()
    }

    setState((prev) => ({
      ...prev,
      isRecording: false,
      isPaused: false,
      audioLevel: 0,
    }))
  }, [])

  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.pause()
      setState((prev) => ({ ...prev, isPaused: true }))
    }
  }, [])

  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
      mediaRecorderRef.current.resume()
      setState((prev) => ({ ...prev, isPaused: false }))
    }
  }, [])

  const clearRecording = useCallback(() => {
    chunksRef.current = []
    setState((prev) => ({
      ...prev,
      audioBlob: null,
      duration: 0,
      error: null,
    }))
  }, [])

  return {
    ...state,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    clearRecording,
  }
}

