import { useAccessibilitySettings } from '../hooks/useAccessibilitySettings'

// Small indicator showing current accessibility features active
export function AccessibilityIndicator() {
  const settings = useAccessibilitySettings()
  
  const activeFeatures = []
  if (settings.highContrast) activeFeatures.push('High Contrast')
  if (settings.largeText) activeFeatures.push('Large Text')
  if (settings.reducedMotion) activeFeatures.push('Reduced Motion')
  if (settings.textSize !== 'medium') activeFeatures.push(`Text: ${settings.textSize}`)
  if (settings.iconSize !== 'medium') activeFeatures.push(`Icons: ${settings.iconSize}`)
  
  if (activeFeatures.length === 0) return null
  
  return (
    <div
      className="fixed top-4 right-4 z-30 px-2 py-1 bg-surface border border-border rounded text-caption text-text-secondary"
      role="status"
      aria-live="polite"
    >
      <span className="sr-only">Active accessibility features: {activeFeatures.join(', ')}</span>
      <span aria-hidden="true">♿ {activeFeatures.length}</span>
    </div>
  )
}
