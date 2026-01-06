import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Volume2, 
  Download, 
  ChevronLeft,
  Play,
  Loader2,
  Check,
  AlertCircle,
  Pause
} from 'lucide-react'
import { Button, Card, Input, Modal } from '../components'
import { api, type SynthesizeResult } from '../lib/api'

export function Test() {
  const navigate = useNavigate()
  
  const [text, setText] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [synthesizeResult, setSynthesizeResult] = useState<SynthesizeResult | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [showExportModal, setShowExportModal] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportSuccess, setExportSuccess] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportConfig, setExportConfig] = useState({
    voiceName: 'my_voice',
    checkpointPath: './data/training_outputs/last.ckpt',
    outputPath: './exports',
  })

  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Clean up audio URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
    }
  }, [audioUrl])

  const handleGenerate = async () => {
    if (!text.trim()) return
    
    setIsGenerating(true)
    setSynthesizeResult(null)
    
    // Clean up previous audio
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
      setAudioUrl(null)
    }
    
    try {
      const result = await api.synthesize(text.trim())
      setSynthesizeResult(result)
      
      if (result.success && result.audio_path) {
        // Fetch the audio file and create a blob URL
        try {
          const response = await fetch(`http://127.0.0.1:8765/output/synthesized.wav`)
          if (response.ok) {
            const blob = await response.blob()
            const url = URL.createObjectURL(blob)
            setAudioUrl(url)
          }
        } catch (e) {
          console.log('Could not fetch audio file directly')
        }
      }
    } catch (error) {
      console.error('Failed to generate speech:', error)
      setSynthesizeResult({
        success: false,
        audio_path: null,
        duration_seconds: 0,
        error: error instanceof Error ? error.message : 'Failed to generate speech'
      })
    } finally {
      setIsGenerating(false)
    }
  }

  const handlePlayPause = () => {
    if (!audioRef.current) return
    
    if (isPlaying) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
  }

  const handleExport = async () => {
    setIsExporting(true)
    setExportError(null)
    
    try {
      const result = await api.exportVoice({
        checkpoint_path: exportConfig.checkpointPath,
        output_path: `${exportConfig.outputPath}/${exportConfig.voiceName}.onnx`,
        voice_name: exportConfig.voiceName,
      })
      
      if (result.success) {
        setExportSuccess(true)
      } else {
        setExportError(result.message || 'Export failed')
      }
    } catch (error) {
      console.error('Export failed:', error)
      setExportError(error instanceof Error ? error.message : 'Export failed')
    } finally {
      setIsExporting(false)
    }
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
          Test Your Voice
        </h1>
        <p className="text-body-lg text-text-secondary">
          Type anything to hear your trained voice speak it.
        </p>
      </motion.div>

      {/* Synthesis Card */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <h2 className="text-h3 text-text-primary mb-md">Generate Speech</h2>
          
          <div className="space-y-md">
            <textarea
              className="
                w-full h-32 bg-background border border-border rounded-lg
                px-4 py-3 text-text-primary placeholder:text-text-muted
                resize-none focus:outline-none focus:border-accent focus:shadow-glow
                transition-all duration-fast
              "
              placeholder="Type anything to hear your voice say it..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={isGenerating}
            />

            <div className="flex gap-3">
              <Button
                variant="primary"
                onClick={handleGenerate}
                disabled={!text.trim() || isGenerating}
                className="flex-1"
              >
                {isGenerating ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Volume2 size={18} />
                    Generate Speech
                  </>
                )}
              </Button>

              {audioUrl && (
                <Button variant="secondary" onClick={handlePlayPause}>
                  {isPlaying ? <Pause size={18} /> : <Play size={18} />}
                  {isPlaying ? 'Pause' : 'Play'}
                </Button>
              )}
            </div>
          </div>

          {/* Audio player */}
          {audioUrl && (
            <div className="mt-md">
              <audio
                ref={audioRef}
                src={audioUrl}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={() => setIsPlaying(false)}
                className="w-full"
                controls
              />
            </div>
          )}

          {/* Result message */}
          {synthesizeResult && (
            <div className={`mt-md p-md rounded-lg ${
              synthesizeResult.success 
                ? 'bg-green-500/10 border border-green-500/20' 
                : 'bg-red-500/10 border border-red-500/20'
            }`}>
              <div className="flex items-center gap-2">
                {synthesizeResult.success ? (
                  <>
                    <Check size={16} className="text-green-400" />
                    <p className="text-caption text-green-400">
                      Generated {synthesizeResult.duration_seconds.toFixed(1)}s of audio
                    </p>
                  </>
                ) : (
                  <>
                    <AlertCircle size={16} className="text-red-400" />
                    <p className="text-caption text-red-400">
                      {synthesizeResult.error}
                    </p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Info message */}
          {!synthesizeResult && (
            <div className="mt-md p-md bg-background rounded-lg">
              <p className="text-caption text-text-muted text-center">
                Voice synthesis requires a trained and exported ONNX model.
                Export your model first using the button below.
              </p>
            </div>
          )}
        </Card>
      </motion.div>

      {/* Sample Phrases */}
      <motion.div variants={itemVariants}>
        <Card className="mb-lg">
          <h3 className="text-h3 text-text-primary mb-md">Try These</h3>
          <div className="grid grid-cols-1 gap-2">
            {[
              "Hello, this is my custom voice clone speaking.",
              "The weather today is absolutely beautiful.",
              "I can say anything you want me to say.",
              "This voice was trained using machine learning.",
              "Artificial intelligence is transforming how we create audio content.",
            ].map((sample, i) => (
              <button
                key={i}
                className="
                  text-left p-3 rounded-lg border border-border
                  text-body text-text-secondary
                  hover:border-accent hover:text-text-primary
                  transition-all duration-fast
                "
                onClick={() => setText(sample)}
              >
                "{sample}"
              </button>
            ))}
          </div>
        </Card>
      </motion.div>

      {/* Export Section */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <h2 className="text-h3 text-text-primary mb-md">Export Options</h2>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-background rounded-lg">
              <div>
                <p className="text-body text-text-primary">ONNX Model</p>
                <p className="text-caption text-text-muted">
                  For Piper TTS, Home Assistant, and other applications
                </p>
              </div>
              <Button
                variant="secondary"
                onClick={() => {
                  setShowExportModal(true)
                  setExportSuccess(false)
                  setExportError(null)
                }}
              >
                <Download size={18} />
                Export
              </Button>
            </div>

            <div className="flex items-center justify-between p-4 bg-background rounded-lg opacity-60">
              <div>
                <p className="text-body text-text-primary">Full Checkpoint</p>
                <p className="text-caption text-text-muted">
                  Continue training later or share with others
                </p>
              </div>
              <Button variant="ghost" disabled>
                Coming Soon
              </Button>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Tips */}
      <motion.div variants={itemVariants}>
        <Card className="mb-lg">
          <h3 className="text-h3 text-text-primary mb-md">Tips for Best Results</h3>
          <ul className="space-y-2 text-body text-text-secondary">
            <li className="flex gap-2">
              <span className="text-accent">•</span>
              Keep sentences short and natural for better quality
            </li>
            <li className="flex gap-2">
              <span className="text-accent">•</span>
              Avoid unusual punctuation or formatting
            </li>
            <li className="flex gap-2">
              <span className="text-accent">•</span>
              Longer training (more epochs) generally produces better voices
            </li>
            <li className="flex gap-2">
              <span className="text-accent">•</span>
              More diverse training samples improve pronunciation
            </li>
          </ul>
        </Card>
      </motion.div>

      {/* Navigation */}
      <motion.div variants={itemVariants} className="flex justify-between">
        <Button variant="ghost" onClick={() => navigate('/train')}>
          <ChevronLeft size={18} />
          Back to Training
        </Button>
        
        <Button variant="primary" onClick={() => navigate('/')}>
          Done
        </Button>
      </motion.div>

      {/* Export Modal */}
      <Modal
        isOpen={showExportModal}
        onClose={() => {
          setShowExportModal(false)
          setExportSuccess(false)
          setExportError(null)
        }}
        title={exportSuccess ? 'Export Complete' : 'Export Voice'}
        footer={
          exportSuccess ? (
            <Button 
              variant="primary" 
              onClick={() => {
                setShowExportModal(false)
                setExportSuccess(false)
              }}
            >
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => setShowExportModal(false)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={handleExport}
                disabled={isExporting}
                isLoading={isExporting}
              >
                Export
              </Button>
            </>
          )
        }
      >
        {exportSuccess ? (
          <div className="text-center py-lg">
            <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-md">
              <Check size={32} className="text-green-400" />
            </div>
            <p className="text-body text-text-primary mb-2">
              Your voice model has been exported successfully.
            </p>
            <p className="text-caption text-text-muted">
              Find your files at: {exportConfig.outputPath}
            </p>
          </div>
        ) : exportError ? (
          <div className="space-y-md">
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-md">
              <div className="flex items-center gap-2">
                <AlertCircle size={16} className="text-red-400" />
                <p className="text-caption text-red-400">{exportError}</p>
              </div>
            </div>
            
            <Input
              label="Voice Name"
              value={exportConfig.voiceName}
              onChange={(e) => setExportConfig(c => ({ ...c, voiceName: e.target.value }))}
              hint="Used for the output filename"
            />
            
            <Input
              label="Checkpoint Path"
              value={exportConfig.checkpointPath}
              onChange={(e) => setExportConfig(c => ({ ...c, checkpointPath: e.target.value }))}
              hint="Path to the trained checkpoint file"
            />
            
            <Input
              label="Output Directory"
              value={exportConfig.outputPath}
              onChange={(e) => setExportConfig(c => ({ ...c, outputPath: e.target.value }))}
              hint="Where to save the exported model"
            />
          </div>
        ) : (
          <div className="space-y-md">
            <Input
              label="Voice Name"
              value={exportConfig.voiceName}
              onChange={(e) => setExportConfig(c => ({ ...c, voiceName: e.target.value }))}
              hint="Used for the output filename"
            />
            
            <Input
              label="Checkpoint Path"
              value={exportConfig.checkpointPath}
              onChange={(e) => setExportConfig(c => ({ ...c, checkpointPath: e.target.value }))}
              hint="Path to the trained checkpoint file"
            />
            
            <Input
              label="Output Directory"
              value={exportConfig.outputPath}
              onChange={(e) => setExportConfig(c => ({ ...c, outputPath: e.target.value }))}
              hint="Where to save the exported model"
            />
          </div>
        )}
      </Modal>
    </motion.div>
  )
}
