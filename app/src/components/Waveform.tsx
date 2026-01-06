import { useRef, useEffect, useCallback } from 'react'

interface WaveformProps {
  audioLevel: number // 0-1
  isRecording: boolean
  className?: string
  barCount?: number
}

export function Waveform({ 
  audioLevel, 
  isRecording, 
  className = '',
  barCount = 32 
}: WaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number>(0)
  const barsRef = useRef<number[]>(new Array(barCount).fill(0))

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { width, height } = canvas
    const barWidth = width / barCount - 2
    const gap = 2

    // Clear canvas
    ctx.clearRect(0, 0, width, height)

    // Update bars
    if (isRecording) {
      // Shift bars left
      for (let i = 0; i < barCount - 1; i++) {
        barsRef.current[i] = barsRef.current[i + 1]
      }
      // Add new bar with some randomness for visual interest
      const noise = Math.random() * 0.2 - 0.1
      barsRef.current[barCount - 1] = Math.min(1, Math.max(0.05, audioLevel + noise))
    } else {
      // Decay bars when not recording
      barsRef.current = barsRef.current.map(v => v * 0.95)
    }

    // Draw bars
    barsRef.current.forEach((level, i) => {
      const barHeight = Math.max(4, level * (height - 8))
      const x = i * (barWidth + gap)
      const y = (height - barHeight) / 2

      // Create gradient
      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight)
      gradient.addColorStop(0, '#FF4F36')
      gradient.addColorStop(1, '#FF6B54')

      ctx.fillStyle = level > 0.1 ? gradient : '#2A2C2F'
      ctx.beginPath()
      ctx.roundRect(x, y, barWidth, barHeight, 2)
      ctx.fill()
    })

    animationRef.current = requestAnimationFrame(draw)
  }, [audioLevel, isRecording, barCount])

  useEffect(() => {
    animationRef.current = requestAnimationFrame(draw)
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [draw])

  // Handle resize
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        canvas.width = width * window.devicePixelRatio
        canvas.height = height * window.devicePixelRatio
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
        }
      }
    })

    resizeObserver.observe(canvas)
    return () => resizeObserver.disconnect()
  }, [])

  return (
    <div className={`bg-surface border border-border rounded-lg p-4 ${className}`}>
      <canvas
        ref={canvasRef}
        className="w-full h-16"
        style={{ width: '100%', height: '64px' }}
      />
    </div>
  )
}

