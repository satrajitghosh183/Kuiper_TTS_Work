import { useEffect, useCallback, useState } from 'react'
import { api } from '../lib/api'
import { useAppStore } from '../store/appStore'

export function useSystemInfo() {
  const { 
    systemCheck, 
    isSystemChecking, 
    setSystemCheck, 
    setIsSystemChecking 
  } = useAppStore()
  
  const [error, setError] = useState<string | null>(null)

  const checkSystem = useCallback(async () => {
    setIsSystemChecking(true)
    setError(null)
    
    try {
      const result = await api.systemCheck()
      setSystemCheck(result)
      return result
    } catch (err) {
      console.error('System check failed:', err)
      setSystemCheck(null)
      
      const errorMessage = err instanceof Error 
        ? err.message 
        : 'Failed to check system. Make sure the backend is running.'
      setError(errorMessage)
      
      throw err
    } finally {
      setIsSystemChecking(false)
    }
  }, [setSystemCheck, setIsSystemChecking])

  useEffect(() => {
    if (!systemCheck && !isSystemChecking) {
      checkSystem().catch(() => {
        // System check failed, likely server not running
      })
    }
  }, [systemCheck, isSystemChecking, checkSystem])

  return {
    systemCheck,
    isChecking: isSystemChecking,
    error,
    refetch: checkSystem,
  }
}
