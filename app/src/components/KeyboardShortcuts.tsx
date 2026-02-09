import { useState, useEffect } from 'react'
import { HelpCircle } from 'lucide-react'
import { Modal } from './Modal'
import { Button } from './Button'

export function KeyboardShortcuts() {
  const [isOpen, setIsOpen] = useState(false)
  
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Press ? to open shortcuts (but not if typing in an input)
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
        const target = e.target as HTMLElement
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault()
          setIsOpen(true)
        }
      }
      
      // Press Escape to close
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])
  
  const shortcuts = [
    { key: 'Space', description: 'Start/Stop recording' },
    { key: 'S', description: 'Save draft recording' },
    { key: 'R', description: 'Redo (discard and restart)' },
    { key: 'P', description: 'Play/Replay current recording' },
    { key: 'T', description: 'Hear pronunciation' },
    { key: 'Esc', description: 'Cancel recording' },
    { key: '← →', description: 'Navigate lines' },
    { key: '↑ ↓', description: 'Navigate scripts' },
    { key: '?', description: 'Show keyboard shortcuts' },
  ]
  
  return (
    <>
      {/* Quick access - show in header */}
      <button
        onClick={() => setIsOpen(true)}
        className="text-text-secondary hover:text-text-primary transition-colors touch-target p-1"
        aria-label="Show keyboard shortcuts"
      >
        <HelpCircle size={18} />
      </button>
      
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Keyboard Shortcuts">
        <dl className="space-y-3">
          {shortcuts.map(({ key, description }) => (
            <div key={key} className="flex justify-between items-center py-2 border-b border-border last:border-0">
              <dt className="text-body text-text-secondary">{description}</dt>
              <dd>
                <kbd className="px-2 py-1 bg-surface border border-border rounded text-caption font-mono">
                  {key}
                </kbd>
              </dd>
            </div>
          ))}
        </dl>
        <div className="pt-4 mt-4 border-t border-border">
          <Button variant="ghost" onClick={() => setIsOpen(false)} className="w-full">
            Close
          </Button>
        </div>
      </Modal>
    </>
  )
}
