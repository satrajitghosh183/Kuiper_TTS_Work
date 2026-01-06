import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Play, 
  Pause, 
  Square, 
  Volume2, 
  ChevronLeft,
  ChevronRight,
  TrendingDown,
  Clock,
  Zap
} from 'lucide-react'
import { Button, Card, Progress, Modal, Input } from '../components'
import { api, createTrainingWebSocket, type TrainingStatus } from '../lib/api'
import { useAppStore } from '../store/appStore'

export function Train() {
  const navigate = useNavigate()
  const { systemCheck } = useAppStore()
  
  const [status, setStatus] = useState<TrainingStatus | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [scanData, setScanData] = useState<any>(null)
  const [isScanning, setIsScanning] = useState(true)
  const [config, setConfig] = useState({
    voiceName: 'my_voice',
    batchSize: systemCheck?.can_train ? 32 : 8,
    maxEpochs: 2000,
    recordingsDir: './recordings',
    outputDir: './data',
  })
  const [lossHistory, setLossHistory] = useState<number[]>([])

  // Scan for existing data on mount
  useEffect(() => {
    const scan = async () => {
      setIsScanning(true)
      try {
        const data = await api.scanTrainingData()
        setScanData(data)
        
        // Auto-update config with found paths
        if (data.recordings_dir_exists) {
          setConfig(prev => ({
            ...prev,
            recordingsDir: data.recordings_dir
          }))
        }
      } catch (error) {
        console.error('Failed to scan data:', error)
      } finally {
        setIsScanning(false)
      }
    }
    scan()
  }, [])

  // Connect to training WebSocket
  useEffect(() => {
    const ws = createTrainingWebSocket((update) => {
      setStatus(update)
      if (update.loss > 0) {
        setLossHistory(prev => [...prev.slice(-50), update.loss])
      }
    })

    return () => ws.close()
  }, [])

  // Fetch initial status
  useEffect(() => {
    api.getTrainingStatus().then(setStatus).catch(() => {})
  }, [])

  const handleStartTraining = async () => {
    setIsStarting(true)
    setShowConfigModal(false)
    
    try {
      // First prepare the data
      const prepResult = await api.prepareTraining({
        recordings_dir: config.recordingsDir,
        output_dir: config.outputDir,
        voice_name: config.voiceName,
      })

      if (!prepResult.success) {
        console.error('Preparation failed:', prepResult.errors)
        return
      }

      // Then start training
      await api.startTraining({
        metadata_path: prepResult.metadata_path,
        audio_dir: prepResult.audio_dir,
        output_dir: config.outputDir,
        voice_name: config.voiceName,
        batch_size: config.batchSize,
        max_epochs: config.maxEpochs,
      })
    } catch (error) {
      console.error('Failed to start training:', error)
    } finally {
      setIsStarting(false)
    }
  }

  const handlePause = async () => {
    try {
      await api.pauseTraining()
    } catch (error) {
      console.error('Failed to pause:', error)
    }
  }

  const handleStop = async () => {
    try {
      await api.stopTraining()
    } catch (error) {
      console.error('Failed to stop:', error)
    }
  }

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`
    if (seconds < 3600) {
      const mins = Math.floor(seconds / 60)
      const secs = Math.round(seconds % 60)
      return `${mins}m ${secs}s`
    }
    const hours = Math.floor(seconds / 3600)
    const mins = Math.round((seconds % 3600) / 60)
    return `${hours}h ${mins}m`
  }

  const isTraining = status?.status === 'training'
  const isPaused = status?.status === 'paused'
  const isCompleted = status?.status === 'completed'
  const isFailed = status?.status === 'failed'

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
          {isTraining ? 'Training Your Voice' : 
           isCompleted ? 'Training Complete' :
           isFailed ? 'Training Failed' : 'Train Voice Model'}
        </h1>
        <p className="text-body-lg text-text-secondary">
          {isTraining ? 'Training is in progress. This may take a while.' :
           isCompleted ? 'Your voice model is ready to use.' :
           isFailed ? 'Something went wrong during training.' :
           'Configure and start training your voice model.'}
        </p>
      </motion.div>

      {/* Progress Card */}
      {(isTraining || isPaused || isCompleted) && status && (
        <motion.div variants={itemVariants}>
          <Card variant="elevated" className="mb-lg">
            <div className="flex items-center justify-between mb-md">
              <div>
                <p className="text-caption text-text-muted">Epoch</p>
                <p className="text-h2 text-text-primary">
                  {status.epoch} <span className="text-text-muted">/ {status.total_epochs}</span>
                </p>
              </div>
              <div className={`
                px-3 py-1 rounded-full text-caption font-medium
                ${isTraining ? 'bg-green-500/10 text-green-400' :
                  isPaused ? 'bg-yellow-500/10 text-yellow-400' :
                  'bg-accent/10 text-accent'}
              `}>
                {status.status.toUpperCase()}
              </div>
            </div>

            <Progress 
              value={status.percent_complete} 
              size="lg"
              showLabel
              label="Progress"
              className="mb-lg"
            />

            {/* Stats Grid */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-background p-md rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingDown size={16} className="text-accent" />
                  <span className="text-caption text-text-muted">Loss</span>
                </div>
                <p className="text-h3 text-text-primary font-mono">
                  {status.loss.toFixed(4)}
                </p>
              </div>

              <div className="bg-background p-md rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <Clock size={16} className="text-text-muted" />
                  <span className="text-caption text-text-muted">Elapsed</span>
                </div>
                <p className="text-h3 text-text-primary font-mono">
                  {formatTime(status.elapsed_seconds)}
                </p>
              </div>

              <div className="bg-background p-md rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <Zap size={16} className="text-text-muted" />
                  <span className="text-caption text-text-muted">Remaining</span>
                </div>
                <p className="text-h3 text-text-primary font-mono">
                  ~{formatTime(status.estimated_remaining_seconds)}
                </p>
              </div>
            </div>

            {/* Loss Chart */}
            {lossHistory.length > 1 && (
              <div className="mt-lg pt-lg border-t border-border">
                <p className="text-caption text-text-muted mb-2">Loss Over Time</p>
                <div className="h-24 flex items-end gap-1">
                  {lossHistory.map((loss, i) => {
                    const maxLoss = Math.max(...lossHistory)
                    const height = (loss / maxLoss) * 100
                    return (
                      <div
                        key={i}
                        className="flex-1 bg-accent rounded-t"
                        style={{ height: `${height}%` }}
                      />
                    )
                  })}
                </div>
              </div>
            )}

            {/* Message */}
            {status.message && (
              <p className="mt-md text-caption text-text-secondary">
                {status.message}
              </p>
            )}
          </Card>
        </motion.div>
      )}

      {/* Controls */}
      <motion.div variants={itemVariants} className="mb-lg">
        <div className="flex items-center justify-center gap-4">
          {!isTraining && !isPaused && !isCompleted && (
            <Button
              variant="primary"
              onClick={() => setShowConfigModal(true)}
              disabled={isStarting}
              isLoading={isStarting}
            >
              <Play size={18} />
              Start Training
            </Button>
          )}

          {isTraining && (
            <>
              <Button variant="secondary" onClick={handlePause}>
                <Pause size={18} />
                Pause
              </Button>
              <Button variant="ghost" onClick={handleStop}>
                <Square size={18} />
                Stop
              </Button>
            </>
          )}

          {isPaused && (
            <>
              <Button variant="primary" onClick={handleStartTraining}>
                <Play size={18} />
                Resume
              </Button>
              <Button variant="ghost" onClick={handleStop}>
                <Square size={18} />
                Stop
              </Button>
            </>
          )}

          {isCompleted && (
            <Button variant="primary" onClick={() => navigate('/test')}>
              <Volume2 size={18} />
              Test Voice
            </Button>
          )}
        </div>

        {(isTraining || isPaused) && (
          <p className="text-center text-caption text-text-muted mt-4">
            Training will auto-save checkpoints every 100 epochs
          </p>
        )}
      </motion.div>

      {/* Data Scan Results */}
      {!isTraining && !isPaused && !isCompleted && scanData && (
        <motion.div variants={itemVariants} className="mb-lg">
          <Card>
            <h3 className="text-h3 text-text-primary mb-md">Found Data</h3>
            
            {isScanning ? (
              <p className="text-body text-text-secondary">Scanning for recordings...</p>
            ) : (
              <div className="space-y-md">
                <div>
                  <p className="text-caption text-text-muted mb-1">Recordings Directory</p>
                  <p className="text-body text-text-primary">
                    {scanData.recordings_dir} 
                    {scanData.recordings_dir_exists ? (
                      <span className="text-green-400 ml-2">✓ Found</span>
                    ) : (
                      <span className="text-yellow-400 ml-2">⚠ Not found</span>
                    )}
                  </p>
                  {scanData.recordings_count > 0 && (
                    <p className="text-caption text-text-secondary mt-1">
                      {scanData.recordings_count} recording{scanData.recordings_count !== 1 ? 's' : ''} found
                    </p>
                  )}
                </div>

                {scanData.text_files.length > 0 && (
                  <div>
                    <p className="text-caption text-text-muted mb-1">Text Files</p>
                    <div className="space-y-1">
                      {scanData.text_files.map((file: any) => (
                        <p key={file.path} className="text-body text-text-secondary">
                          {file.name} ({file.line_count} lines)
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                {scanData.recordings.length > 0 && (
                  <div>
                    <p className="text-caption text-text-muted mb-1">Matched Recordings</p>
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {scanData.recordings.slice(0, 10).map((rec: any) => (
                        <p key={rec.path} className="text-caption text-text-secondary">
                          {rec.filename} {rec.has_text ? '✓' : '⚠'}
                        </p>
                      ))}
                      {scanData.recordings.length > 10 && (
                        <p className="text-caption text-text-muted">
                          ... and {scanData.recordings.length - 10} more
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {scanData.warnings.length > 0 && (
                  <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-md">
                    <p className="text-caption text-yellow-400 font-medium mb-1">Warnings</p>
                    {scanData.warnings.map((w: string, i: number) => (
                      <p key={i} className="text-caption text-yellow-300">{w}</p>
                    ))}
                  </div>
                )}

                {scanData.recordings_count === 0 && scanData.recordings_dir_exists && (
                  <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-md">
                    <p className="text-caption text-yellow-400">
                      No recordings found. Record some audio first.
                    </p>
                  </div>
                )}
              </div>
            )}
          </Card>
        </motion.div>
      )}

      {/* Info Cards */}
      {!isTraining && !isPaused && !isCompleted && (
        <motion.div variants={itemVariants}>
          <div className="grid grid-cols-2 gap-4 mb-lg">
            <Card>
              <h3 className="text-h3 text-text-primary mb-2">What happens next?</h3>
              <ol className="space-y-2 text-body text-text-secondary">
                <li className="flex gap-2">
                  <span className="text-accent">1.</span>
                  Your recordings are processed into spectrograms
                </li>
                <li className="flex gap-2">
                  <span className="text-accent">2.</span>
                  The model learns from your voice patterns
                </li>
                <li className="flex gap-2">
                  <span className="text-accent">3.</span>
                  After training, you can synthesize new speech
                </li>
              </ol>
            </Card>

            <Card>
              <h3 className="text-h3 text-text-primary mb-2">Tips</h3>
              <ul className="space-y-2 text-body text-text-secondary">
                <li>Keep your computer plugged in</li>
                <li>Close other GPU-intensive applications</li>
                <li>Training can be paused and resumed</li>
                <li>More recordings = better quality</li>
              </ul>
            </Card>
          </div>
        </motion.div>
      )}

      {/* Navigation */}
      <motion.div variants={itemVariants} className="flex justify-between">
        <Button 
          variant="ghost" 
          onClick={() => navigate('/record')}
          disabled={isTraining}
        >
          <ChevronLeft size={18} />
          Back
        </Button>
        
        <Button 
          variant={isCompleted ? 'primary' : 'secondary'}
          onClick={() => navigate('/test')}
          disabled={!isCompleted}
        >
          Test Voice
          <ChevronRight size={18} />
        </Button>
      </motion.div>

      {/* Config Modal */}
      <Modal
        isOpen={showConfigModal}
        onClose={() => setShowConfigModal(false)}
        title="Training Configuration"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowConfigModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleStartTraining}>
              Start Training
            </Button>
          </>
        }
      >
        <div className="space-y-md">
          <Input
            label="Voice Name"
            value={config.voiceName}
            onChange={(e) => setConfig(c => ({ ...c, voiceName: e.target.value }))}
            placeholder="my_voice"
          />
          
          <Input
            label="Recordings Directory"
            value={config.recordingsDir}
            onChange={(e) => setConfig(c => ({ ...c, recordingsDir: e.target.value }))}
            hint="Path to directory containing WAV files"
          />
          
          <Input
            label="Output Directory"
            value={config.outputDir}
            onChange={(e) => setConfig(c => ({ ...c, outputDir: e.target.value }))}
            hint="Where to save training data and checkpoints"
          />
          
          <Input
            label="Batch Size"
            type="number"
            value={config.batchSize}
            onChange={(e) => setConfig(c => ({ ...c, batchSize: parseInt(e.target.value) || 32 }))}
            hint="Larger = faster but uses more memory"
          />
          
          <Input
            label="Max Epochs"
            type="number"
            value={config.maxEpochs}
            onChange={(e) => setConfig(c => ({ ...c, maxEpochs: parseInt(e.target.value) || 2000 }))}
            hint="More epochs = better quality but longer training"
          />
        </div>
      </Modal>
    </motion.div>
  )
}

