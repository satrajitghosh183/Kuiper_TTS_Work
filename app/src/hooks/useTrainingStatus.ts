import { useEffect, useRef } from 'react'
import { createTrainingWebSocket, type TrainingStatus } from '../lib/api'
import { useAppStore } from '../store/appStore'

export function useTrainingStatus() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  
  const { 
    trainingStatus, 
    isTrainingConnected,
    setTrainingStatus, 
    setIsTrainingConnected 
  } = useAppStore()

  useEffect(() => {
    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return

      wsRef.current = createTrainingWebSocket(
        (status: TrainingStatus) => {
          setTrainingStatus(status)
          setIsTrainingConnected(true)
        },
        () => {
          setIsTrainingConnected(false)
          // Attempt reconnect after 3 seconds
          reconnectTimeoutRef.current = window.setTimeout(connect, 3000)
        }
      )

      wsRef.current.onopen = () => {
        setIsTrainingConnected(true)
      }

      wsRef.current.onclose = () => {
        setIsTrainingConnected(false)
        // Attempt reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [setTrainingStatus, setIsTrainingConnected])

  return {
    status: trainingStatus,
    isConnected: isTrainingConnected,
  }
}

