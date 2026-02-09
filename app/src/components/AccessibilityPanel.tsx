import { useState, useEffect } from 'react'
import { Accessibility } from 'lucide-react'
import { Modal } from './Modal'
import { Button } from './Button'
import { Toggle } from './Toggle'

interface AccessibilitySettings {
  highContrast: boolean
  largeText: boolean
  reducedMotion: boolean
  screenReaderAnnouncements: boolean
  keyboardShortcutsEnabled: boolean
  textSize: 'small' | 'medium' | 'large' | 'extra-large'
  iconSize: 'small' | 'medium' | 'large'
}

export function AccessibilityPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [settings, setSettings] = useState<AccessibilitySettings>(() => {
    // Load from localStorage
    try {
      const saved = localStorage.getItem('accessibility-settings')
      if (saved) {
        return JSON.parse(saved)
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
    // Apply settings to document
    document.documentElement.classList.toggle('high-contrast', settings.highContrast)
    document.documentElement.classList.toggle('large-text', settings.largeText)
    document.documentElement.classList.toggle('reduced-motion', settings.reducedMotion)
    
    // Apply text size
    document.documentElement.setAttribute('data-text-size', settings.textSize)
    
    // Apply icon size
    document.documentElement.setAttribute('data-icon-size', settings.iconSize)
    
    // Save to localStorage
    try {
      localStorage.setItem('accessibility-settings', JSON.stringify(settings))
    } catch (error) {
      console.error('Failed to save accessibility settings:', error)
    }
  }, [settings])
  
  return (
    <>
      {/* Quick access button - always visible */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 z-40 p-3 rounded-full bg-accent text-white shadow-lg touch-target"
        aria-label="Open accessibility settings"
        aria-expanded={isOpen}
      >
        <Accessibility size={20} />
      </button>
      
      {/* Settings panel */}
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Accessibility Settings">
        <div className="space-y-4">
          <Toggle
            label="High Contrast Mode"
            checked={settings.highContrast}
            onChange={(checked) => setSettings({ ...settings, highContrast: checked })}
          />
          
          <Toggle
            label="Large Text"
            checked={settings.largeText}
            onChange={(checked) => setSettings({ ...settings, largeText: checked })}
          />
          
          <Toggle
            label="Reduce Motion"
            checked={settings.reducedMotion}
            onChange={(checked) => setSettings({ ...settings, reducedMotion: checked })}
          />
          
          <Toggle
            label="Screen Reader Announcements"
            checked={settings.screenReaderAnnouncements}
            onChange={(checked) => setSettings({ ...settings, screenReaderAnnouncements: checked })}
          />
          
          <Toggle
            label="Keyboard Shortcuts Enabled"
            checked={settings.keyboardShortcutsEnabled}
            onChange={(checked) => setSettings({ ...settings, keyboardShortcutsEnabled: checked })}
          />
          
          <div className="pt-4 border-t border-border space-y-3">
            {/* Text Size Control */}
            <div>
              <label className="text-body text-text-primary mb-2 block">
                Text Size
              </label>
              <div className="flex gap-2">
                {(['small', 'medium', 'large', 'extra-large'] as const).map((size) => (
                  <button
                    key={size}
                    onClick={() => setSettings({ ...settings, textSize: size })}
                    className={`
                      flex-1 px-3 py-2 rounded border transition-colors
                      ${settings.textSize === size
                        ? 'bg-accent border-accent text-white'
                        : 'bg-surface border-border text-text-secondary hover:border-accent'}
                    `}
                  >
                    <span className="text-caption capitalize">{size.replace('-', ' ')}</span>
                  </button>
                ))}
              </div>
            </div>
            
            {/* Icon Size Control */}
            <div>
              <label className="text-body text-text-primary mb-2 block">
                Icon Size
              </label>
              <div className="flex gap-2">
                {(['small', 'medium', 'large'] as const).map((size) => (
                  <button
                    key={size}
                    onClick={() => setSettings({ ...settings, iconSize: size })}
                    className={`
                      flex-1 px-3 py-2 rounded border transition-colors
                      ${settings.iconSize === size
                        ? 'bg-accent border-accent text-white'
                        : 'bg-surface border-border text-text-secondary hover:border-accent'}
                    `}
                  >
                    <span className="text-caption capitalize">{size}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          <div className="pt-4 border-t border-border">
            <Button variant="ghost" onClick={() => setIsOpen(false)} className="w-full">
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </>
  )
}
