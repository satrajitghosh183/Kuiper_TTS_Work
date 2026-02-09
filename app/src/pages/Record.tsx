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
  Loader2,
  Download,
  Play
} from 'lucide-react'
import { Button, Card, Progress, Waveform, Tooltip, KeyboardShortcuts, AccessibilityPanel, AccessibilityIndicator } from '../components'
import { api, type Recording as RecordingType, type Script } from '../lib/api'
import { useAppStore } from '../store/appStore'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import { useRecorderStatePersistence } from '../hooks/useRecorderStatePersistence'
import { useScreenReader } from '../hooks/useScreenReader'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useOnlineStatus } from '../hooks/useOnlineStatus'

export function Record() {
  const navigate = useNavigate()
  const { recommendedGain, selectedDeviceId } = useAppStore()
  const isMobile = useMediaQuery('(max-width: 640px)')
  const isTablet = useMediaQuery('(min-width: 641px) and (max-width: 1024px)')
  const isOnline = useOnlineStatus()
  
  const [scripts, setScripts] = useState<Script[]>([])
  const [currentScriptIndex, setCurrentScriptIndex] = useState(0)
  const [currentLineIndex, setCurrentLineIndex] = useState(0)
  const [recordings, setRecordings] = useState<Map<string, RecordingType>>(new Map())
  const [isPlayingBack, setIsPlayingBack] = useState(false)
  const [, setIsLoadingRecordings] = useState(true)
  const [isLoadingScripts, setIsLoadingScripts] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [recorderState, setRecorderState] = useState<'idle' | 'recording' | 'draft' | 'saved'>('idle')
  const [draftBlob, setDraftBlob] = useState<Blob | null>(null)
  const [isRestoring, setIsRestoring] = useState(true)
  const [isPronouncing, setIsPronouncing] = useState(false)
  const { announce } = useScreenReader()

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
    autoSave: false, // Don't auto-save - use draft mode
    silenceThreshold: 0.01, // RMS threshold for silence detection
    silenceDurationMs: 2000, // 2 seconds of silence before auto-stop
    maxDurationMs: 30000, // 30 second max duration
    onDataAvailable: async (blob) => {
      // Don't auto-save - set as draft instead
      setDraftBlob(blob)
      setRecorderState('draft')
      announce('Recording stopped. Press S to save.')
    }
  })

  // State persistence
  const { restoreState, autoSave, lastSaved } = useRecorderStatePersistence(
    {
      currentScriptIndex,
      currentLineIndex,
      recorderState,
      isRecording,
      duration,
      draftBlob: draftBlob || audioBlob ? {
        recordingKey,
        blob: draftBlob || audioBlob!,
        timestamp: Date.now(),
      } : undefined,
      autoSkipRecorded: true,
      autoStartNext: false,
      silenceThreshold: 0.01,
      silenceDurationMs: 2000,
      maxDurationMs: 30000,
      lastSaved: 0,
      version: '1.0.0',
    },
    recordings,
    scripts
  )

  // Restore state on mount
  useEffect(() => {
    const restore = async () => {
      setIsRestoring(true)
      const savedState = await restoreState()
      
      if (savedState) {
        // Restore scripts (if not already loaded)
        if (savedState.scripts.length > 0 && scripts.length === 0) {
          setScripts(savedState.scripts)
        }
        
        // Restore recordings
        const recordingsMap = new Map(savedState.recordings)
        setRecordings(recordingsMap)
        
        // Restore position
        if (savedState.session.currentScriptIndex < scripts.length) {
          setCurrentScriptIndex(savedState.session.currentScriptIndex)
        }
        if (savedState.session.currentLineIndex < (scripts[savedState.session.currentScriptIndex]?.lines.length || 0)) {
          setCurrentLineIndex(savedState.session.currentLineIndex)
        }
        
        // Restore draft blob if exists
        if (savedState.session.draftBlob) {
          setDraftBlob(savedState.session.draftBlob.blob)
          setRecorderState('draft')
        }
        
        // Show restoration notification
        const restoreTime = new Date(savedState.timestamp).toLocaleTimeString()
        announce(`Restored session from ${restoreTime}`)
      }
      
      setIsRestoring(false)
    }
    
    // Only restore after scripts are loaded
    if (!isLoadingScripts) {
      restore()
    }
  }, [isLoadingScripts])

  // Handle save draft
  const handleSave = async () => {
    const blobToSave = draftBlob || audioBlob
    if (!blobToSave || recorderState !== 'draft') return
    
    try {
      setSaveError(null)
      const filename = `${recordingKey}.wav`
      const result = await api.saveRecording(blobToSave, filename, recommendedGain)
      
      if (result.success) {
        setRecordings(prev => new Map(prev).set(recordingKey, {
          filename,
          text: currentLine,
          duration_seconds: result.duration_seconds,
          is_valid: true,
          error: null,
        }))
        setRecorderState('saved')
        setDraftBlob(null)
        clearRecording()
        announce('Recording saved')
        
        // Auto-skip to next unrecorded line
        setTimeout(() => {
          findNextUnrecordedLine()
        }, 500)
      } else {
        setSaveError(result.error || 'Failed to save recording')
      }
    } catch (error) {
      console.error('Failed to save recording:', error)
      setSaveError(error instanceof Error ? error.message : 'Failed to save recording')
    }
  }

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
      } else if (e.code === 'KeyS' && !e.repeat && recorderState === 'draft') {
        e.preventDefault()
        handleSave()
      } else if (e.code === 'KeyR' && !e.repeat && (recorderState === 'draft' || recorderState === 'saved')) {
        e.preventDefault()
        handleRedo()
      } else if (e.code === 'KeyP' && !e.repeat) {
        e.preventDefault()
        playRecording()
      } else if (e.code === 'KeyT' && !e.repeat) {
        e.preventDefault()
        handlePronounce()
      } else if (e.code === 'Escape' && (recorderState === 'recording' || recorderState === 'draft')) {
        e.preventDefault()
        handleCancel()
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
  }, [isRecording, currentLineIndex, currentScriptIndex, scripts, recorderState, handleRecord, handleSave, handleRedo, playRecording, handlePronounce, handleCancel, handleNext, handlePrev, currentLine])

  const handleRecord = useCallback(async () => {
    if (isRecording) {
      stopRecording()
      setRecorderState('draft')
    } else {
      clearRecording()
      setSaveError(null)
      setDraftBlob(null)
      setRecorderState('recording')
      const deviceId = selectedDeviceId?.toString()
      await startRecording(deviceId)
      announce('Recording started')
    }
  }, [isRecording, stopRecording, clearRecording, startRecording, selectedDeviceId, announce])

  // Auto-skip to next unrecorded line
  const findNextUnrecordedLine = useCallback(() => {
    if (scripts.length === 0) return
    
    for (let scriptIdx = currentScriptIndex; scriptIdx < scripts.length; scriptIdx++) {
      const script = scripts[scriptIdx]
      const startLineIdx = scriptIdx === currentScriptIndex ? currentLineIndex + 1 : 0
      
      for (let lineIdx = startLineIdx; lineIdx < script.lines.length; lineIdx++) {
        const key = `${script.name}_${(lineIdx + 1).toString().padStart(4, '0')}`
        if (!recordings.has(key)) {
          setCurrentScriptIndex(scriptIdx)
          setCurrentLineIndex(lineIdx)
          return true
        }
      }
    }
    return false
  }, [scripts, currentScriptIndex, currentLineIndex, recordings])

  const handleNext = () => {
    if (!currentScript) return
    
    if (currentLineIndex < currentScript.lines.length - 1) {
      setCurrentLineIndex(prev => prev + 1)
    } else if (currentScriptIndex < scripts.length - 1) {
      setCurrentScriptIndex(prev => prev + 1)
      setCurrentLineIndex(0)
    }
    clearRecording()
    setDraftBlob(null)
    setRecorderState('idle')
    setSaveError(null)
  }

  // Auto-skip on mount and after save
  useEffect(() => {
    if (!isRestoring && scripts.length > 0 && recordings.size > 0) {
      const key = `${scripts[currentScriptIndex]?.name}_${(currentLineIndex + 1).toString().padStart(4, '0')}`
      if (recordings.has(key)) {
        findNextUnrecordedLine()
      }
    }
  }, [recordings, scripts, currentScriptIndex, currentLineIndex, isRestoring, findNextUnrecordedLine])

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
    setDraftBlob(null)
    setRecorderState('idle')
    setSaveError(null)
    announce('Recording discarded')
  }

  const handleCancel = () => {
    if (recorderState === 'recording' || recorderState === 'draft') {
      stopRecording()
      clearRecording()
      setDraftBlob(null)
      setRecorderState('idle')
      setSaveError(null)
      announce('Recording cancelled')
    }
  }

  const handleDownloadRecordings = async () => {
    try {
      const blob = await api.downloadRecordings()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `recordings-${new Date().toISOString().split('T')[0]}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      announce('Recordings downloaded')
    } catch (error) {
      console.error('Failed to download recordings:', error)
      setSaveError(error instanceof Error ? error.message : 'Failed to download recordings')
    }
  }

  const handlePronounce = async () => {
    if (!currentLine) return
    
    try {
      setIsPronouncing(true)
      const blob = await api.pronounceText(currentLine)
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.play()
      audio.onended = () => {
        setIsPronouncing(false)
        URL.revokeObjectURL(url)
      }
      announce('Playing pronunciation')
    } catch (error) {
      console.error('Failed to generate pronunciation:', error)
      setIsPronouncing(false)
      setSaveError(error instanceof Error ? error.message : 'Failed to generate pronunciation')
    }
  }

  const playRecording = async () => {
    const blobToPlay = draftBlob || audioBlob
    if (!blobToPlay) {
      // Try to load saved recording
      const savedRecording = recordings.get(recordingKey)
      if (savedRecording) {
        // Would need API endpoint to get recording URL
        announce('Saved recording playback not yet implemented')
        return
      }
      return
    }
    
    setIsPlayingBack(true)
    const url = URL.createObjectURL(blobToPlay)
    const audio = new Audio(url)
    audio.play()
    audio.onended = () => {
      setIsPlayingBack(false)
      URL.revokeObjectURL(url)
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

  // Show restoration indicator
  if (isRestoring) {
    return (
      <motion.div
        className="max-w-4xl mx-auto flex flex-col items-center justify-center min-h-[60vh]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <Loader2 size={48} className="animate-spin text-accent mb-4" />
        <p className="text-body-lg text-text-secondary">Restoring session...</p>
      </motion.div>
    )
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
        className="max-w-4xl mx-auto container-responsive"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Offline indicator */}
        {!isOnline && (
          <motion.div 
            variants={itemVariants}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-lg"
          >
            <Card className="bg-yellow-500/10 border-yellow-500/20">
              <div className="flex items-center gap-2">
                <AlertCircle size={16} className="text-yellow-400" />
                <p className="text-caption text-yellow-400">
                  You're offline. Recordings will be queued and synced when you're back online.
                </p>
              </div>
            </Card>
          </motion.div>
        )}

        {/* Header - Compact */}
        <motion.div variants={itemVariants} className={`${isMobile ? 'mb-md' : 'mb-lg'}`}>
          <div className={`flex ${isMobile ? 'flex-col gap-1' : 'items-center justify-between'} mb-2`}>
            <h1 className={`text-text-primary ${isMobile ? 'text-h2' : 'text-h1'}`}>Recording Studio</h1>
            <div className={`flex ${isMobile ? 'flex-row items-center' : 'items-center'} gap-2`}>
              <span className={`text-text-secondary ${isMobile ? 'text-caption' : 'text-body'}`}>
                {recordedCount}/{totalLines}
              </span>
              {recordings.size > 0 && (
                <Tooltip content="Download my recordings" placement="bottom">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDownloadRecordings}
                    aria-label="Download my recordings"
                    className="touch-target p-1"
                  >
                    <Download size={14} />
                  </Button>
                </Tooltip>
              )}
              <KeyboardShortcuts />
            </div>
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

      {/* Current Line Card - Compact for low-res */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <div className={`text-center ${isMobile ? 'py-md' : 'py-lg'}`}>
            <AnimatePresence mode="wait">
              <motion.p
                key={`${currentScriptIndex}-${currentLineIndex}`}
                className={`text-text-primary leading-relaxed ${isMobile ? 'text-h3' : 'text-h2'}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.2 }}
              >
                "{currentLine}"
              </motion.p>
            </AnimatePresence>
          </div>
          
          <div className="flex items-center justify-center gap-2 mt-2">
            <div className={`text-center text-text-muted ${isMobile ? 'text-micro' : 'text-caption'}`}>
              Line {currentLineIndex + 1}/{currentScript?.lines.length || 0} · {currentScript?.name || 'No script'}
            </div>
            {currentLine && (
              <Tooltip content="Hear pronunciation (T)" placement="top">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handlePronounce}
                  disabled={isPronouncing}
                  aria-label="Hear pronunciation"
                  className="touch-target p-1"
                >
                  <Play size={14} />
                </Button>
              </Tooltip>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Waveform - Compact for low-res */}
      <motion.div variants={itemVariants} className={`mb-lg ${isMobile ? 'mb-md' : ''}`}>
        <Waveform 
          audioLevel={audioLevel} 
          isRecording={isRecording}
          barCount={isMobile ? 32 : 48}
        />
        
        {isRecording && (
          <div className="text-center mt-1">
            <span className={`text-accent font-mono ${isMobile ? 'text-body' : 'text-body-lg'}`}>
              {formatDuration(duration)}
            </span>
          </div>
        )}
      </motion.div>

        {/* Controls - Compact layout for speed */}
        <motion.div variants={itemVariants} className="mb-lg">
          <div className={`flex items-center justify-center gap-2 ${isMobile ? 'flex-col' : 'flex-row'}`}>
            <Tooltip content="Previous line (←)" placement="top" delay={300}>
              <Button
                variant="ghost"
                onClick={handlePrev}
                disabled={currentLineIndex === 0 && currentScriptIndex === 0}
                aria-label="Previous line"
                size="sm"
                className={`touch-target ${isMobile ? 'w-full' : ''}`}
              >
                <SkipBack size={16} />
              </Button>
            </Tooltip>

            {/* Main record button */}
            <Tooltip content={isRecording ? "Stop recording (Space)" : "Start recording (Space)"} placement="top">
              <Button
                variant={isRecording ? 'secondary' : 'primary'}
                onClick={handleRecord}
                className={`!rounded-full !p-0 touch-target ${isMobile ? '!w-16 !h-16' : '!w-14 !h-14'}`}
                disabled={!currentScript}
                aria-label={isRecording ? "Stop recording" : "Start recording"}
              >
                {isRecording ? (
                  <Square size={20} className="fill-current" />
                ) : (
                  <Mic size={22} />
                )}
              </Button>
            </Tooltip>

            {/* Replay button - always visible when there's something to play */}
            <Tooltip content="Play current recording (P)" placement="top" delay={300}>
              <Button
                variant="ghost"
                onClick={playRecording}
                disabled={!draftBlob && !audioBlob && !hasRecording || isPlayingBack}
                aria-label="Play recording"
                size="sm"
                className={`touch-target ${isMobile ? 'w-full' : ''}`}
              >
                <Volume2 size={16} />
              </Button>
            </Tooltip>

            <Tooltip content="Next line (→)" placement="top" delay={300}>
              <Button
                variant="ghost"
                onClick={handleNext}
                disabled={
                  !currentScript ||
                  (currentLineIndex === currentScript.lines.length - 1 && 
                  currentScriptIndex === scripts.length - 1)
                }
                aria-label="Next line"
                size="sm"
                className={`touch-target ${isMobile ? 'w-full' : ''}`}
              >
                <SkipForward size={16} />
              </Button>
            </Tooltip>
          </div>
          
          {/* Quick action buttons - compact row */}
          {(recorderState === 'draft' || recorderState === 'saved') && (
            <div className="flex items-center justify-center gap-2 mt-3">
              {recorderState === 'draft' && (
                <>
                  <Tooltip content="Save (S)" placement="top">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleSave}
                      className="text-caption px-3 py-1.5"
                    >
                      Save (S)
                    </Button>
                  </Tooltip>
                  <Tooltip content="Redo (R)" placement="top">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleRedo}
                      className="text-caption px-3 py-1.5"
                    >
                      Redo (R)
                    </Button>
                  </Tooltip>
                </>
              )}
              {recorderState === 'saved' && (
                <Tooltip content="Redo (R)" placement="top">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRedo}
                    className="text-caption px-3 py-1.5"
                  >
                    Redo (R)
                  </Button>
                </Tooltip>
              )}
            </div>
          )}

        <p className={`text-center text-text-muted mt-2 ${isMobile ? 'text-micro' : 'text-caption'}`}>
          SPACE: record/stop · S: save · R: redo · P: play · Esc: cancel
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

      {/* Save indicator */}
      {lastSaved > 0 && Date.now() - lastSaved < 2000 && (
        <motion.div 
          variants={itemVariants}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="fixed bottom-4 left-4 z-30 px-3 py-2 bg-surface border border-border rounded-lg text-caption text-text-secondary shadow-lg"
        >
          Saved
        </motion.div>
      )}

      {/* Draft state - compact notification */}
      {recorderState === 'draft' && draftBlob && (
        <motion.div 
          variants={itemVariants}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
        >
          <Card className={`bg-blue-500/10 border-blue-500/20 ${isMobile ? 'mb-md py-2' : 'mb-lg py-3'}`}>
            <div className={`flex items-center justify-between ${isMobile ? 'flex-col gap-2' : ''}`}>
              <div className="flex items-center gap-2">
                <AlertCircle size={14} className="text-blue-400" />
                <span className={`text-text-primary ${isMobile ? 'text-caption' : 'text-body'}`}>
                  Draft ready · S to save · R to redo
                </span>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Saved notification - compact */}
      {(recorderState === 'saved' && hasRecording) && !saveError && (
        <motion.div 
          variants={itemVariants}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
        >
          <Card className={`${isMobile ? 'mb-md py-2' : 'mb-lg py-3'}`}>
            <div className={`flex items-center justify-between ${isMobile ? 'flex-col gap-2' : ''}`}>
              <div className="flex items-center gap-2">
                <Check size={14} className="text-green-400" />
                <span className={`text-text-primary ${isMobile ? 'text-caption' : 'text-body'}`}>
                  Saved · {formatDuration(duration || recordings.get(recordingKey)?.duration_seconds || 0)}
                </span>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Recent Recordings List - Compact, hidden on very small screens */}
      {recordings.size > 0 && !isMobile && (
        <motion.div variants={itemVariants}>
          <Card className={`${isMobile ? 'mb-md' : 'mb-lg'}`}>
            <h3 className={`text-text-primary mb-2 ${isMobile ? 'text-h3 text-caption' : 'text-h3'}`}>Recent</h3>
            <div className={`space-y-1 ${isMobile ? 'max-h-24' : 'max-h-32'} overflow-y-auto`}>
              {Array.from(recordings.entries())
                .slice(-5)
                .reverse()
                .map(([key, rec]) => (
                  <div 
                    key={key}
                    className={`flex items-center justify-between border-b border-border last:border-0 ${isMobile ? 'py-1' : 'py-1.5'}`}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Check size={12} className="text-green-400 flex-shrink-0" />
                      <span className={`text-text-secondary truncate ${isMobile ? 'text-micro' : 'text-caption'}`}>
                        {rec.text.length > (isMobile ? 25 : 35) ? rec.text.substring(0, isMobile ? 25 : 35) + '...' : rec.text}
                      </span>
                    </div>
                    <span className={`text-text-muted font-mono flex-shrink-0 ml-2 ${isMobile ? 'text-micro' : 'text-caption'}`}>
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
      
      {/* Accessibility components */}
      <AccessibilityPanel />
      <AccessibilityIndicator />
    </motion.div>
  )
}
