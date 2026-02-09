import { useState, useEffect } from 'react'

interface AccessibilitySettings {
  highContrast: boolean
  largeText: boolean
  reducedMotion: boolean
  screenReaderAnnouncements: boolean
  keyboardShortcutsEnabled: boolean
  textSize: 'small' | 'medium' | 'large' | 'extra-large'
  iconSize: 'small' | 'medium' | 'large'
}

export function useAccessibilitySettings() {
  const [settings, setSettings] = useState<AccessibilitySettings>(() => {
    try {
      const saved = localStorage.getItem('accessibility-settings')
      if (saved) {
        const parsed = JSON.parse(saved)
        return {
          highContrast: parsed.highContrast || false,
          largeText: parsed.largeText || false,
          reducedMotion: parsed.reducedMotion || window.matchMedia('(prefers-reduced-motion: reduce)').matches,
          screenReaderAnnouncements: parsed.screenReaderAnnouncements !== false,
          keyboardShortcutsEnabled: parsed.keyboardShortcutsEnabled !== false,
          textSize: parsed.textSize || 'medium',
          iconSize: parsed.iconSize || 'medium',
        }
      }
    } catch (error) {
      console.error('Failed to load accessibility settings:', error)
    }
    
    return {
      highContrast: false,
      largeText: false,
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      screenReaderAnnouncements: true,
      keyboardShortcutsEnabled: true,
      textSize: 'medium',
      iconSize: 'medium',
    }
  })

  useEffect(() => {
    const handleStorageChange = () => {
      try {
        const saved = localStorage.getItem('accessibility-settings')
        if (saved) {
          const parsed = JSON.parse(saved)
          setSettings({
            highContrast: parsed.highContrast || false,
            largeText: parsed.largeText || false,
            reducedMotion: parsed.reducedMotion || false,
            screenReaderAnnouncements: parsed.screenReaderAnnouncements !== false,
            keyboardShortcutsEnabled: parsed.keyboardShortcutsEnabled !== false,
            textSize: parsed.textSize || 'medium',
            iconSize: parsed.iconSize || 'medium',
          })
        }
      } catch (error) {
        console.error('Failed to load accessibility settings:', error)
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [])

  return settings
}
