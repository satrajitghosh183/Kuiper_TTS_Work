import { useEffect, useCallback, useRef } from 'react'
import { RecordingSessionState, PersistedState } from '../types/recorderState'
import { StatePersistenceManager } from '../lib/statePersistence'
import { Recording, Script } from '../lib/api'

const AUTO_SAVE_INTERVAL = 5000 // 5 seconds
const DEBOUNCE_DELAY = 1000 // 1 second

export function useRecorderStatePersistence(
  state: RecordingSessionState,
  recordings: Map<string, Recording>,
  scripts: Script[]
) {
  const persistenceManager = useRef<StatePersistenceManager | null>(null)
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const lastSavedRef = useRef<number>(0)
  
  // Initialize persistence manager
  useEffect(() => {
    persistenceManager.current = new StatePersistenceManager()
    persistenceManager.current.init().catch(console.error)
  }, [])
  
  // Debounced auto-save
  const autoSave = useCallback(() => {
    if (!persistenceManager.current) return
    
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }
    
    saveTimeoutRef.current = setTimeout(async () => {
      if (!persistenceManager.current) return
      
      const persistedState: PersistedState = {
        session: {
          ...state,
          lastSaved: Date.now(),
        },
        recordings: Array.from(recordings.entries()),
        scripts,
        timestamp: Date.now(),
      }
      
      try {
        await persistenceManager.current.save(persistedState)
        lastSavedRef.current = Date.now()
      } catch (error) {
        console.error('Failed to auto-save state:', error)
      }
    }, DEBOUNCE_DELAY)
  }, [state, recordings, scripts])
  
  // Auto-save on state changes
  useEffect(() => {
    autoSave()
    
    // Also save on visibility change (user switching tabs)
    const handleVisibilityChange = () => {
      if (document.hidden) {
        autoSave()
      }
    }
    
    // Save before page unload
    const handleBeforeUnload = () => {
      autoSave()
    }
    
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)
    
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [autoSave])
  
  // Periodic auto-save (every 5 seconds)
  useEffect(() => {
    const interval = setInterval(() => {
      const timeSinceLastSave = Date.now() - lastSavedRef.current
      if (timeSinceLastSave >= AUTO_SAVE_INTERVAL) {
        autoSave()
      }
    }, AUTO_SAVE_INTERVAL)
    
    return () => clearInterval(interval)
  }, [autoSave])
  
  // Restore state on mount
  const restoreState = useCallback(async (): Promise<PersistedState | null> => {
    if (!persistenceManager.current) {
      persistenceManager.current = new StatePersistenceManager()
      await persistenceManager.current.init()
    }
    
    try {
      return await persistenceManager.current.load()
    } catch (error) {
      console.error('Failed to restore state:', error)
      return null
    }
  }, [])
  
  return {
    autoSave,
    restoreState,
    lastSaved: lastSavedRef.current,
  }
}
