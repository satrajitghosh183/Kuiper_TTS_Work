import { useState, useRef, useEffect, ReactElement } from 'react'

interface TooltipProps {
  content: string | ReactElement
  children: ReactElement
  placement?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number // Delay before showing (default: 500ms)
  disabled?: boolean
  className?: string
}

export function Tooltip({ 
  content, 
  children, 
  placement = 'top',
  delay = 500,
  disabled = false,
  className = ''
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  
  const handleMouseEnter = () => {
    if (disabled) return
    
    const id = setTimeout(() => {
      setIsVisible(true)
    }, delay)
    setTimeoutId(id)
  }
  
  const handleMouseLeave = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      setTimeoutId(null)
    }
    setIsVisible(false)
  }

  const handleFocus = () => {
    if (disabled) return
    setIsVisible(true)
  }

  const handleBlur = () => {
    setIsVisible(false)
  }
  
  // Smart positioning based on viewport
  useEffect(() => {
    if (isVisible && tooltipRef.current && triggerRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect()
      const tooltipRect = tooltipRef.current.getBoundingClientRect()
      const viewport = { width: window.innerWidth, height: window.innerHeight }
      
      // Calculate position with viewport bounds checking
      let top = 0
      let left = 0
      let actualPlacement = placement
      
      switch (placement) {
        case 'top':
          top = triggerRect.top - tooltipRect.height - 8
          left = triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2)
          if (top < 0) actualPlacement = 'bottom'
          break
        case 'bottom':
          top = triggerRect.bottom + 8
          left = triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2)
          if (top + tooltipRect.height > viewport.height) actualPlacement = 'top'
          break
        case 'left':
          left = triggerRect.left - tooltipRect.width - 8
          top = triggerRect.top + (triggerRect.height / 2) - (tooltipRect.height / 2)
          if (left < 0) actualPlacement = 'right'
          break
        case 'right':
          left = triggerRect.right + 8
          top = triggerRect.top + (triggerRect.height / 2) - (tooltipRect.height / 2)
          if (left + tooltipRect.width > viewport.width) actualPlacement = 'left'
          break
      }
      
      // Recalculate if placement changed
      if (actualPlacement !== placement) {
        switch (actualPlacement) {
          case 'top':
            top = triggerRect.top - tooltipRect.height - 8
            left = triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2)
            break
          case 'bottom':
            top = triggerRect.bottom + 8
            left = triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2)
            break
          case 'left':
            left = triggerRect.left - tooltipRect.width - 8
            top = triggerRect.top + (triggerRect.height / 2) - (tooltipRect.height / 2)
            break
          case 'right':
            left = triggerRect.right + 8
            top = triggerRect.top + (triggerRect.height / 2) - (tooltipRect.height / 2)
            break
        }
      }
      
      // Ensure tooltip stays within viewport
      left = Math.max(8, Math.min(left, viewport.width - tooltipRect.width - 8))
      top = Math.max(8, Math.min(top, viewport.height - tooltipRect.height - 8))
      
      setPosition({ top, left })
    }
  }, [isVisible, placement])
  
  return (
    <div
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
    >
      {children}
      
      {isVisible && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={`
            fixed z-50 px-2 py-1
            bg-surface border border-border rounded
            text-caption text-text-primary
            shadow-lg
            pointer-events-none
            animate-fade-in
            ${className}
          `}
          style={{
            top: `${position.top}px`,
            left: `${position.left}px`,
          }}
        >
          {content}
        </div>
      )}
    </div>
  )
}
