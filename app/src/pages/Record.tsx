import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Mic, 
  Square, 
  SkipForward, 
  SkipBack, 
  RefreshCw, 
  ChevronRight,
  ChevronLeft,
  Check,
  Volume2,
  AlertCircle,
  Loader2
} from 'lucide-react'
import { Button, Card, Progress, Waveform } from '../components'
import { api, type Recording as RecordingType, type Script } from '../lib/api'
import { useAppStore } from '../store/appStore'
import { useAudioRecorder } from '../hooks/useAudioRecorder'

export function Record() {
  const navigate = useNavigate()
  const { recommendedGain, selectedDeviceId } = useAppStore()
  
  const [scripts, setScripts] = useState<Script[]>([])
  const [currentScriptIndex, setCurrentScriptIndex] = useState(0)
  const [currentLineIndex, setCurrentLineIndex] = useState(0)
  const [recordings, setRecordings] = useState<Map<string, RecordingType>>(new Map())
  const [isPlayingBack, setIsPlayingBack] = useState(false)
  const [, setIsLoadingRecordings] = useState(true)
  const [isLoadingScripts, setIsLoadingScripts] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Load scripts from backend
  useEffect(() => {
    const loadScripts = async () => {
      try {
        setIsLoadingScripts(true)
        setError(null)
        const loadedScripts = await api.listScripts()
        
        if (loadedScripts.length === 0) {
          setError('No text scripts found. Add .txt files to the project directory.')
        } else {
          setScripts(loadedScripts)
        }
      } catch (err) {
        console.error('Failed to load scripts:', err)
        setError('Failed to load scripts. Make sure the backend is running.')
      } finally {
        setIsLoadingScripts(false)
      }
    }
    
    loadScripts()
  }, [])

  // Load existing recordings on mount
  useEffect(() => {
    const loadRecordings = async () => {
      try {
        const existing = await api.listRecordings()
        const recordingsMap = new Map<string, RecordingType>()
        
        existing.forEach(rec => {
          // Extract key from filename (e.g., "phoneme_coverage_0001.wav" -> "phoneme_coverage_0001")
          const key = rec.filename.replace('.wav', '')
          recordingsMap.set(key, rec)
        })
        
        setRecordings(recordingsMap)
      } catch (error) {
        console.error('Failed to load recordings:', error)
      } finally {
        setIsLoadingRecordings(false)
      }
    }
    
    loadRecordings()
  }, [])

  const currentScript = scripts[currentScriptIndex]
  const currentLine = currentScript?.lines[currentLineIndex] || ''
  const recordingKey = currentScript 
    ? `${currentScript.name}_${(currentLineIndex + 1).toString().padStart(4, '0')}`
    : ''
  const hasRecording = recordings.has(recordingKey)

  const totalLines = scripts.reduce((sum, s) => sum + s.lines.length, 0)
  const recordedCount = recordings.size
  const progressPercent = totalLines > 0 ? (recordedCount / totalLines) * 100 : 0

  const {
    isRecording,
    audioLevel,
    audioBlob,
    duration,
    startRecording,
    stopRecording,
    clearRecording,
  } = useAudioRecorder({
    onDataAvailable: async (blob) => {
      // Save recording to backend
      try {
        setSaveError(null)
        const filename = `${recordingKey}.wav`
        const result = await api.saveRecording(blob, filename, recommendedGain)
        
        if (result.success) {
          setRecordings(prev => new Map(prev).set(recordingKey, {
            filename,
            text: currentLine,
            duration_seconds: result.duration_seconds,
            is_valid: true,
            error: null,
          }))
        } else {
          setSaveError(result.error || 'Failed to save recording')
        }
      } catch (error) {
        console.error('Failed to save recording:', error)
        setSaveError(error instanceof Error ? error.message : 'Failed to save recording')
      }
    }
  })

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }
      
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault()
        handleRecord()
      } else if (e.code === 'ArrowRight') {
        e.preventDefault()
        handleNext()
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault()
        handlePrev()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isRecording, currentLineIndex, currentScriptIndex, scripts])

  const handleRecord = useCallback(async () => {
    if (isRecording) {
      stopRecording()
    } else {
      clearRecording()
      setSaveError(null)
      const deviceId = selectedDeviceId?.toString()
      await startRecording(deviceId)
    }
  }, [isRecording, stopRecording, clearRecording, startRecording, selectedDeviceId])

  const handleNext = () => {
    if (!currentScript) return
    
    if (currentLineIndex < currentScript.lines.length - 1) {
      setCurrentLineIndex(prev => prev + 1)
    } else if (currentScriptIndex < scripts.length - 1) {
      setCurrentScriptIndex(prev => prev + 1)
      setCurrentLineIndex(0)
    }
    clearRecording()
    setSaveError(null)
  }

  const handlePrev = () => {
    if (!currentScript) return
    
    if (currentLineIndex > 0) {
      setCurrentLineIndex(prev => prev - 1)
    } else if (currentScriptIndex > 0) {
      setCurrentScriptIndex(prev => prev - 1)
      const prevScript = scripts[currentScriptIndex - 1]
      setCurrentLineIndex(prevScript.lines.length - 1)
    }
    clearRecording()
    setSaveError(null)
  }

  const handleRedo = () => {
    recordings.delete(recordingKey)
    setRecordings(new Map(recordings))
    clearRecording()
    setSaveError(null)
  }

  const playRecording = () => {
    if (audioBlob) {
      setIsPlayingBack(true)
      const url = URL.createObjectURL(audioBlob)
      const audio = new Audio(url)
      audio.play()
      audio.onended = () => {
        setIsPlayingBack(false)
        URL.revokeObjectURL(url)
      }
    }
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
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

  // Loading state
  if (isLoadingScripts) {
    return (
      <motion.div
        className="max-w-4xl mx-auto flex flex-col items-center justify-center min-h-[60vh]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <Loader2 size={48} className="animate-spin text-accent mb-4" />
        <p className="text-body-lg text-text-secondary">Loading scripts...</p>
      </motion.div>
    )
  }

  // Error state
  if (error && scripts.length === 0) {
    return (
      <motion.div
        className="max-w-4xl mx-auto"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <Card variant="elevated" className="text-center py-xl">
          <AlertCircle size={48} className="text-accent mx-auto mb-4" />
          <h2 className="text-h2 text-text-primary mb-2">No Scripts Found</h2>
          <p className="text-body text-text-secondary mb-lg max-w-md mx-auto">
            {error}
          </p>
          <div className="flex gap-4 justify-center">
            <Button variant="ghost" onClick={() => navigate('/setup')}>
              <ChevronLeft size={18} />
              Back
            </Button>
            <Button variant="primary" onClick={() => window.location.reload()}>
              <RefreshCw size={18} />
              Retry
            </Button>
          </div>
        </Card>
      </motion.div>
    )
  }

  return (
    <motion.div
      className="max-w-4xl mx-auto"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="mb-lg">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-h1 text-text-primary">Recording Studio</h1>
          <span className="text-body text-text-secondary">
            {recordedCount}/{totalLines}
          </span>
        </div>
        <Progress 
          value={progressPercent} 
          size="md"
          className="mb-2"
        />
        
        {/* Script selector */}
        {scripts.length > 1 && (
          <div className="flex gap-2 flex-wrap mt-4">
            {scripts.map((script, idx) => {
              // Count recordings for this script
              const scriptRecordings = Array.from(recordings.keys()).filter(
                key => key.startsWith(script.name + '_')
              ).length
              const isComplete = scriptRecordings >= script.lines.length
              
              return (
                <button
                  key={script.name}
                  onClick={() => {
                    setCurrentScriptIndex(idx)
                    setCurrentLineIndex(0)
                    clearRecording()
                  }}
                  className={`
                    px-3 py-1.5 rounded-full text-caption font-medium transition-all
                    ${idx === currentScriptIndex
                      ? 'bg-accent text-white'
                      : isComplete
                        ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                        : 'bg-surface text-text-secondary hover:bg-surface-elevated'}
                  `}
                >
                  {script.name} ({scriptRecordings}/{script.lines.length})
                </button>
              )
            })}
          </div>
        )}
      </motion.div>

      {/* Current Line Card */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <div className="text-center py-xl">
            <AnimatePresence mode="wait">
              <motion.p
                key={`${currentScriptIndex}-${currentLineIndex}`}
                className="text-h2 text-text-primary leading-relaxed"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.2 }}
              >
                "{currentLine}"
              </motion.p>
            </AnimatePresence>
          </div>
          
          <div className="text-center text-caption text-text-muted">
            Line {currentLineIndex + 1} of {currentScript?.lines.length || 0} · {currentScript?.name || 'No script'}
          </div>
        </Card>
      </motion.div>

      {/* Waveform */}
      <motion.div variants={itemVariants} className="mb-lg">
        <Waveform 
          audioLevel={audioLevel} 
          isRecording={isRecording}
          barCount={48}
        />
        
        {isRecording && (
          <div className="text-center mt-2">
            <span className="text-body-lg text-accent font-mono">
              {formatDuration(duration)}
            </span>
          </div>
        )}
      </motion.div>

      {/* Controls */}
      <motion.div variants={itemVariants} className="mb-lg">
        <div className="flex items-center justify-center gap-4">
          <Button
            variant="ghost"
            onClick={handlePrev}
            disabled={currentLineIndex === 0 && currentScriptIndex === 0}
          >
            <SkipBack size={20} />
          </Button>

          <Button
            variant={isRecording ? 'secondary' : 'primary'}
            onClick={handleRecord}
            className="!w-20 !h-20 !rounded-full !p-0"
            disabled={!currentScript}
          >
            {isRecording ? (
              <Square size={24} className="fill-current" />
            ) : (
              <Mic size={28} />
            )}
          </Button>

          <Button
            variant="ghost"
            onClick={handleNext}
            disabled={
              !currentScript ||
              (currentLineIndex === currentScript.lines.length - 1 && 
              currentScriptIndex === scripts.length - 1)
            }
          >
            <SkipForward size={20} />
          </Button>
        </div>

        <p className="text-center text-caption text-text-muted mt-4">
          Press SPACE to record · Arrow keys to navigate
        </p>
      </motion.div>

      {/* Save Error */}
      {saveError && (
        <motion.div 
          variants={itemVariants}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
        >
          <Card className="mb-lg bg-red-500/10 border-red-500/20">
            <div className="flex items-center gap-3">
              <AlertCircle size={20} className="text-red-400" />
              <p className="text-body text-red-400">{saveError}</p>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Recent Recording */}
      {(audioBlob || hasRecording) && !saveError && (
        <motion.div 
          variants={itemVariants}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
        >
          <Card className="mb-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center">
                  <Check size={16} className="text-green-400" />
                </div>
                <div>
                  <p className="text-body text-text-primary">Recording saved</p>
                  <p className="text-caption text-text-muted">
                    {recordingKey}.wav · {formatDuration(duration || recordings.get(recordingKey)?.duration_seconds || 0)}
                  </p>
                </div>
              </div>
              
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={playRecording}
                  disabled={!audioBlob || isPlayingBack}
                >
                  <Volume2 size={16} />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRedo}
                >
                  <RefreshCw size={16} />
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Recent Recordings List */}
      {recordings.size > 0 && (
        <motion.div variants={itemVariants}>
          <Card className="mb-lg">
            <h3 className="text-h3 text-text-primary mb-md">Recent Recordings</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {Array.from(recordings.entries())
                .slice(-5)
                .reverse()
                .map(([key, rec]) => (
                  <div 
                    key={key}
                    className="flex items-center justify-between py-2 border-b border-border last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <Check size={14} className="text-green-400" />
                      <span className="text-caption text-text-secondary truncate max-w-xs">
                        {rec.text.length > 40 ? rec.text.substring(0, 40) + '...' : rec.text}
                      </span>
                    </div>
                    <span className="text-micro text-text-muted font-mono">
                      {rec.duration_seconds.toFixed(1)}s
                    </span>
                  </div>
                ))}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Navigation */}
      <motion.div variants={itemVariants} className="flex justify-between">
        <Button variant="ghost" onClick={() => navigate('/setup')}>
          <ChevronLeft size={18} />
          Back
        </Button>
        
        <Button 
          variant="primary" 
          onClick={() => navigate('/train')}
          disabled={recordings.size === 0}
        >
          Start Training
          <ChevronRight size={18} />
        </Button>
      </motion.div>
    </motion.div>
  )
}
