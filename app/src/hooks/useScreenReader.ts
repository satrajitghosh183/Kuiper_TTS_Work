import { useCallback } from 'react'

export function useScreenReader() {
  const announce = useCallback((message: string, priority: 'polite' | 'assertive' = 'polite') => {
    const id = `sr-announcement-${Date.now()}`
    const announcement = document.createElement('div')
    announcement.id = id
    announcement.setAttribute('role', 'status')
    announcement.setAttribute('aria-live', priority)
    announcement.setAttribute('aria-atomic', 'true')
    announcement.className = 'sr-only'
    announcement.textContent = message
    
    document.body.appendChild(announcement)
    
    // Remove after announcement
    setTimeout(() => {
      const element = document.getElementById(id)
      if (element) {
        document.body.removeChild(element)
      }
    }, 1000)
  }, [])
  
  return { announce }
}
