import { ReactNode } from 'react'
import { useAccessibilitySettings } from '../hooks/useAccessibilitySettings'

interface IconProps {
  children: ReactNode
  size?: number
  className?: string
}

/**
 * Wrapper component that applies icon size scaling based on accessibility settings
 */
export function Icon({ children, size, className = '' }: IconProps) {
  const { iconSize } = useAccessibilitySettings()
  
  const scaleMap = {
    small: 0.75,
    medium: 1,
    large: 1.5,
  }
  
  const scale = scaleMap[iconSize]
  const scaledSize = size ? size * scale : undefined
  
  return (
    <span 
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        transform: scale !== 1 ? `scale(${scale})` : undefined,
        transformOrigin: 'center',
      }}
    >
      {children}
    </span>
  )
}
