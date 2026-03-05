import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Cpu, 
  HardDrive, 
  MemoryStick, 
  Gauge, 
  ChevronRight, 
  AlertTriangle, 
  Check, 
  X, 
  Loader2,
  WifiOff,
  RefreshCw
} from 'lucide-react'
import { Button, Card, StatusBadge } from '../components'
import { useSystemInfo } from '../hooks/useSystemInfo'
import { api } from '../lib/api'

export function Welcome() {
  const navigate = useNavigate()
  const { systemCheck, isChecking, refetch, error: systemError } = useSystemInfo()
  const [serverAvailable, setServerAvailable] = useState<boolean | null>(null)
  const [checkTimeout, setCheckTimeout] = useState(false)
  
  // Debug logging
  useEffect(() => {
    console.log('Welcome page mounted, serverAvailable:', serverAvailable)
  }, [serverAvailable])
  const [estimates, setEstimates] = useState<{
    time100: string
    time500: string
    time1000: string
    batchSize: number
    epochs: number
  } | null>(null)

  // Check server availability with timeout
  useEffect(() => {
    let mounted = true
    
    const checkServer = async () => {
      try {
        // Add timeout to prevent hanging
        const timeoutPromise = new Promise<boolean>((resolve) => {
          setTimeout(() => {
            if (mounted) resolve(false)
          }, 3000) // 3 second timeout
        })
        
        const checkPromise = api.isServerAvailable().catch(() => false)
        const available = await Promise.race([checkPromise, timeoutPromise])
        
        if (mounted) {
          setServerAvailable(available)
        }
      } catch (error) {
        console.error('Server check failed:', error)
        if (mounted) {
          setServerAvailable(false)
        }
      }
    }
    
    checkServer()
    
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    if (systemCheck) {
      // Fetch training estimates
      api.trainingEstimate(500).then((result) => {
        setEstimates({
          time100: '~30m',
          time500: result.estimated_time,
          time1000: '~5h',
          batchSize: result.recommended_batch_size,
          epochs: result.recommended_epochs,
        })
      }).catch(() => {
        // Use defaults
        setEstimates({
          time100: '~30m',
          time500: '~2.5h',
          time1000: '~5h',
          batchSize: 32,
          epochs: 2000,
        })
      })
    }
  }, [systemCheck])

  const getStatusIcon = (condition: boolean | undefined) => {
    if (condition === undefined) return <Loader2 size={16} className="animate-spin text-text-muted" />
    return condition 
      ? <Check size={16} className="text-green-400" /> 
      : <X size={16} className="text-accent" />
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
      },
    },
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 },
  }

  // Server not available
  if (serverAvailable === false) {
    return (
      <motion.div
        className="max-w-4xl mx-auto w-full"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <Card variant="elevated" className="text-center py-xl">
          <WifiOff size={64} className="text-accent mx-auto mb-4" />
          <h1 className="text-h1 text-text-primary mb-2">Server Not Running</h1>
          <p className="text-body-lg text-text-secondary mb-lg max-w-md mx-auto">
            The Kuiper TTS backend server is not available. Please start the server to continue.
          </p>
          
          <div className="bg-surface rounded-lg p-md mb-lg max-w-md mx-auto text-left">
            <p className="text-caption text-text-muted mb-2">Run this command in your terminal:</p>
            <code className="text-body font-mono text-accent">
              python run_server.py
            </code>
          </div>
          
          <Button 
            variant="primary" 
            onClick={async () => {
              setServerAvailable(null)
              const available = await api.isServerAvailable()
              setServerAvailable(available)
              if (available) {
                refetch()
              }
            }}
          >
            <RefreshCw size={18} />
            Retry Connection
          </Button>
        </Card>
      </motion.div>
    )
  }

  // Timeout fallback for server check
  useEffect(() => {
    if (serverAvailable === null && !checkTimeout) {
      const timer = setTimeout(() => {
        console.warn('Server check timed out, showing content anyway')
        setCheckTimeout(true)
        setServerAvailable(false)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [serverAvailable, checkTimeout])

  // Loading server check
  if (serverAvailable === null && !checkTimeout) {
    return (
      <motion.div
        className="max-w-4xl mx-auto flex flex-col items-center justify-center min-h-[60vh]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <Loader2 size={48} className="animate-spin text-accent mb-4" />
        <p className="text-body-lg text-text-secondary">Connecting to server...</p>
      </motion.div>
    )
  }

  return (
    <motion.div
      className="max-w-4xl mx-auto w-full"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="mb-xl">
        <h1 className="text-h1 text-text-primary mb-2">
          Create Your Voice Clone
        </h1>
        <p className="text-body-lg text-text-secondary">
          Let's check if your system can train a voice model.
        </p>
      </motion.div>

      {/* System Check Card */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <div className="flex items-center justify-between mb-md">
            <h2 className="text-h3 text-text-primary">System Analysis</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={refetch}
              disabled={isChecking}
            >
              {isChecking ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                'Refresh'
              )}
            </Button>
          </div>

          {systemError ? (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-md">
              <p className="text-body text-red-400">{systemError}</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* GPU */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-3 border-b border-border">
                <div className="flex items-center gap-3">
                  <Gauge size={20} className="text-text-muted" />
                  <div>
                    <p className="text-body text-text-primary">GPU</p>
                    <p className="text-caption text-text-muted">
                      {systemCheck?.gpu_name || 'Checking...'}
                      {systemCheck?.gpu_vram_gb && ` (${systemCheck.gpu_vram_gb.toFixed(1)} GB VRAM)`}
                    </p>
                  </div>
                </div>
                {getStatusIcon(systemCheck?.gpu_name !== null)}
              </div>

              {/* RAM */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-3 border-b border-border">
                <div className="flex items-center gap-3">
                  <MemoryStick size={20} className="text-text-muted" />
                  <div>
                    <p className="text-body text-text-primary">RAM</p>
                    <p className="text-caption text-text-muted">
                      {systemCheck 
                        ? `${systemCheck.ram_total_gb.toFixed(1)} GB total, ${systemCheck.ram_available_gb.toFixed(1)} GB available`
                        : 'Checking...'}
                    </p>
                  </div>
                </div>
                {getStatusIcon(systemCheck ? systemCheck.ram_total_gb >= 8 : undefined)}
              </div>

              {/* Storage */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-3 border-b border-border">
                <div className="flex items-center gap-3">
                  <HardDrive size={20} className="text-text-muted" />
                  <div>
                    <p className="text-body text-text-primary">Storage</p>
                    <p className="text-caption text-text-muted">
                      {systemCheck 
                        ? `${systemCheck.storage_free_gb.toFixed(1)} GB free`
                        : 'Checking...'}
                    </p>
                  </div>
                </div>
                {getStatusIcon(systemCheck ? systemCheck.storage_free_gb >= 10 : undefined)}
              </div>

              {/* CUDA/MPS */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 py-3">
                <div className="flex items-center gap-3">
                  <Cpu size={20} className="text-text-muted" />
                  <div>
                    <p className="text-body text-text-primary">Acceleration</p>
                    <p className="text-caption text-text-muted">
                      {systemCheck 
                        ? `Backend: ${systemCheck.training_backend.toUpperCase()}`
                        : 'Checking...'}
                    </p>
                  </div>
                </div>
                {getStatusIcon(systemCheck ? systemCheck.training_backend !== 'cpu' : undefined)}
              </div>
            </div>
          )}

          {/* Warnings */}
          {systemCheck?.warnings && systemCheck.warnings.length > 0 && (
            <div className="mt-md pt-md border-t border-border">
              {systemCheck.warnings.map((warning, i) => (
                <div key={i} className="flex items-start gap-2 py-2">
                  <AlertTriangle size={16} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                  <p className="text-caption text-text-secondary">{warning}</p>
                </div>
              ))}
            </div>
          )}

          {/* Errors */}
          {systemCheck?.errors && systemCheck.errors.length > 0 && (
            <div className="mt-md pt-md border-t border-border">
              {systemCheck.errors.map((error, i) => (
                <div key={i} className="flex items-start gap-2 py-2">
                  <X size={16} className="text-accent mt-0.5 flex-shrink-0" />
                  <p className="text-caption text-accent">{error}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>

      {/* Training Estimates */}
      <motion.div variants={itemVariants}>
        <Card variant="elevated" className="mb-lg">
          <h2 className="text-h3 text-text-primary mb-md">Training Estimate</h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-md">
            <div className="text-center p-4 bg-background rounded-lg">
              <p className="text-h2 text-accent mb-1">{estimates?.time100 || '~30m'}</p>
              <p className="text-caption text-text-muted">100 sentences</p>
            </div>
            <div className="text-center p-4 bg-background rounded-lg">
              <p className="text-h2 text-accent mb-1">
                {estimates?.time500 || '~2.5h'}
              </p>
              <p className="text-caption text-text-muted">500 sentences</p>
            </div>
            <div className="text-center p-4 bg-background rounded-lg">
              <p className="text-h2 text-accent mb-1">{estimates?.time1000 || '~5h'}</p>
              <p className="text-caption text-text-muted">1000 sentences</p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 text-caption text-text-secondary">
            <span>Recommended batch size: <span className="text-text-primary font-mono">{estimates?.batchSize || 32}</span></span>
            <span>Optimal epochs: <span className="text-text-primary font-mono">{estimates?.epochs || 2000}</span></span>
          </div>
        </Card>
      </motion.div>

      {/* Overall Status */}
      <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <StatusBadge 
            status={
              isChecking ? 'loading' :
              systemCheck?.can_train ? 'success' : 
              systemCheck ? 'error' : 'idle'
            }
            label={
              isChecking ? 'Checking...' :
              systemCheck?.can_train ? 'Ready to train' :
              systemCheck ? 'Cannot train' : 'Unknown'
            }
          />
        </div>

        <Button
          variant="primary"
          onClick={() => navigate('/setup')}
          disabled={isChecking || !systemCheck?.can_train}
        >
          Continue
          <ChevronRight size={18} />
        </Button>
      </motion.div>
    </motion.div>
  )
}
