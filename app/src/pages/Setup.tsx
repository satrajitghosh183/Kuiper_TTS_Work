import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mic, Volume2, ChevronRight, ChevronLeft, RefreshCw } from 'lucide-react'
import { Button, Card, Slider, Waveform, StatusBadge } from '../components'
import { api } from '../lib/api'
import { useAppStore } from '../store/appStore'
import { useAudioRecorder } from '../hooks/useAudioRecorder'

export function Setup() {
  const navigate = useNavigate()
  const { 
    devices, 
    selectedDeviceId, 
    recommendedGain,
    setDevices, 
    setSelectedDeviceId,
    setRecommendedGain 
  } = useAppStore()

  const [isLoadingDevices, setIsLoadingDevices] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{
    success: boolean
    peakLevel: number
    rmsLevel: number
    isClipping: boolean
  } | null>(null)
  const [gain, setGain] = useState(recommendedGain)

  const {
    isRecording,
    audioLevel,
    audioBlob,
    startRecording,
    stopRecording,
    clearRecording,
  } = useAudioRecorder()

  // Load devices on mount
  useEffect(() => {
    loadDevices()
  }, [])

  const loadDevices = async () => {
    setIsLoadingDevices(true)
    try {
      const result = await api.listDevices()
      setDevices(result)
      
      // Select default device if none selected
      if (selectedDeviceId === null) {
        const defaultDevice = result.find(d => d.is_default)
        if (defaultDevice) {
          setSelectedDeviceId(defaultDevice.device_id)
        }
      }
    } catch (error) {
      console.error('Failed to load devices:', error)
    } finally {
      setIsLoadingDevices(false)
    }
  }

  const testDevice = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
      const result = await api.testDevice(selectedDeviceId ?? undefined, 3.0)
      setTestResult({
        success: result.success,
        peakLevel: result.peak_level,
        rmsLevel: result.rms_level,
        isClipping: result.is_clipping,
      })
      
      if (result.recommended_gain !== gain) {
        setGain(result.recommended_gain)
        setRecommendedGain(result.recommended_gain)
      }
    } catch (error) {
      console.error('Device test failed:', error)
    } finally {
      setIsTesting(false)
    }
  }

  const handleRecordTest = async () => {
    if (isRecording) {
      stopRecording()
    } else {
      clearRecording()
      const deviceId = selectedDeviceId?.toString()
      await startRecording(deviceId)
    }
  }

  const playbackAudio = () => {
    if (audioBlob) {
      const url = URL.createObjectURL(audioBlob)
      const audio = new Audio(url)
      audio.play()
      audio.onended = () => URL.revokeObjectURL(url)
    }
  }

  const handleContinue = () => {
    setRecommendedGain(gain)
    navigate('/record')
  }

  const getLevelStatus = (rms: number): 'success' | 'warning' | 'error' => {
    if (rms < 0.01) return 'error'
    if (rms < 0.05) return 'warning'
    if (rms > 0.5) return 'warning'
    return 'success'
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.05 },
    },
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 },
  }

  return (
    <motion.div
      className="max-w-4xl mx-auto"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="mb-xl">
        <h1 className="text-h1 text-text-primary mb-2">
          Microphone Setup
        </h1>
        <p className="text-body-lg text-text-secondary">
          Configure your microphone for optimal recording quality.
        </p>
      </motion.div>

      {/* Device Selection */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <div className="flex items-center justify-between mb-md">
            <h2 className="text-h3 text-text-primary">Select Microphone</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadDevices}
              disabled={isLoadingDevices}
            >
              <RefreshCw size={16} className={isLoadingDevices ? 'animate-spin' : ''} />
              Refresh
            </Button>
          </div>

          <div className="space-y-2">
            {devices.length === 0 ? (
              <p className="text-caption text-text-muted py-4 text-center">
                {isLoadingDevices ? 'Loading devices...' : 'No microphones found'}
              </p>
            ) : (
              devices.map((device) => (
                <button
                  key={device.device_id}
                  className={`
                    w-full flex items-center gap-3 p-4 rounded-lg
                    border transition-all duration-fast
                    ${selectedDeviceId === device.device_id
                      ? 'bg-accent/10 border-accent text-text-primary'
                      : 'bg-surface border-border text-text-secondary hover:border-text-muted'}
                  `}
                  onClick={() => setSelectedDeviceId(device.device_id)}
                >
                  <div className={`
                    w-4 h-4 rounded-full border-2
                    ${selectedDeviceId === device.device_id
                      ? 'border-accent bg-accent'
                      : 'border-text-muted'}
                  `}>
                    {selectedDeviceId === device.device_id && (
                      <div className="w-2 h-2 bg-background rounded-full m-auto mt-0.5" />
                    )}
                  </div>
                  <div className="flex-1 text-left">
                    <p className="text-body">{device.name}</p>
                    <p className="text-caption text-text-muted">
                      {device.channels} channel{device.channels > 1 ? 's' : ''} · {device.sample_rate} Hz
                      {device.is_default && ' · Default'}
                    </p>
                  </div>
                </button>
              ))
            )}
          </div>
        </Card>
      </motion.div>

      {/* Test Recording */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <h2 className="text-h3 text-text-primary mb-md">Test Recording</h2>
          
          <p className="text-body text-text-secondary mb-md">
            Read this sentence to test your microphone:
          </p>
          
          <div className="bg-background p-md rounded-lg mb-md">
            <p className="text-body-lg text-text-primary text-center italic">
              "The quick brown fox jumps over the lazy dog."
            </p>
          </div>

          <Waveform 
            audioLevel={audioLevel} 
            isRecording={isRecording}
            className="mb-md"
          />

          <div className="flex gap-3 mb-md">
            <Button
              variant={isRecording ? 'secondary' : 'primary'}
              onClick={handleRecordTest}
              className="flex-1"
            >
              <Mic size={18} />
              {isRecording ? 'Stop Recording' : 'Record Test'}
            </Button>
            
            <Button
              variant="secondary"
              onClick={playbackAudio}
              disabled={!audioBlob}
            >
              <Volume2 size={18} />
              Play Back
            </Button>
          </div>

          {/* Auto-test button */}
          <Button
            variant="ghost"
            onClick={testDevice}
            disabled={isTesting || selectedDeviceId === null}
            className="w-full"
          >
            {isTesting ? 'Testing...' : 'Auto-detect optimal settings'}
          </Button>

          {testResult && (
            <div className="mt-md pt-md border-t border-border">
              <div className="flex items-center justify-between">
                <span className="text-caption text-text-secondary">Signal Level</span>
                <StatusBadge 
                  status={getLevelStatus(testResult.rmsLevel)}
                  label={
                    testResult.rmsLevel < 0.01 ? 'Too quiet' :
                    testResult.rmsLevel < 0.05 ? 'Low' :
                    testResult.rmsLevel > 0.5 ? 'High' : 'Good'
                  }
                />
              </div>
              {testResult.isClipping && (
                <p className="text-caption text-accent mt-2">
                  Audio is clipping. Move the microphone further away or reduce gain.
                </p>
              )}
            </div>
          )}
        </Card>
      </motion.div>

      {/* Settings */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <h2 className="text-h3 text-text-primary mb-md">Settings</h2>
          
          <Slider
            label="Gain"
            value={gain}
            min={0.5}
            max={3.0}
            step={0.1}
            onChange={(e) => setGain(parseFloat(e.target.value))}
            valueFormatter={(v) => `${v.toFixed(1)}x`}
            className="mb-md"
          />

          <div className="flex items-center justify-between py-3 border-t border-border">
            <div>
              <p className="text-body text-text-primary">Noise Reduction</p>
              <p className="text-caption text-text-muted">
                Automatically reduce background noise
              </p>
            </div>
            <button className="
              w-12 h-6 rounded-full bg-accent
              relative transition-colors duration-fast
            ">
              <span className="
                absolute top-1 right-1 w-4 h-4 rounded-full bg-white
                transition-transform duration-fast
              " />
            </button>
          </div>
        </Card>
      </motion.div>

      {/* Navigation */}
      <motion.div variants={itemVariants} className="flex justify-between">
        <Button variant="ghost" onClick={() => navigate('/')}>
          <ChevronLeft size={18} />
          Back
        </Button>
        
        <Button variant="primary" onClick={handleContinue}>
          Save & Continue
          <ChevronRight size={18} />
        </Button>
      </motion.div>
    </motion.div>
  )
}

