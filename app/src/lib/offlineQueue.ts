import { api } from './api'

interface QueuedRecording {
  blob: Blob
  filename: string
  gain: number
  timestamp: number
}

const DB_NAME = 'kuiper-offline-queue'
const STORE_NAME = 'queue'

export class OfflineQueue {
  private queue: QueuedRecording[] = []
  private db: IDBDatabase | null = null
  
  async init(): Promise<void> {
    if (this.db) return
    
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        // Load existing queue
        this.loadQueue().then(resolve).catch(reject)
      }
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'timestamp' })
        }
      }
    })
  }
  
  private async loadQueue(): Promise<void> {
    if (!this.db) await this.init()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.getAll()
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.queue = request.result || []
        resolve()
      }
    })
  }
  
  async add(blob: Blob, filename: string, gain: number): Promise<void> {
    await this.init()
    
    const item: QueuedRecording = {
      blob,
      filename,
      gain,
      timestamp: Date.now(),
    }
    
    // Store in IndexedDB
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      
      // Convert blob to ArrayBuffer for storage
      const reader = new FileReader()
      reader.onload = () => {
        const itemToStore = {
          ...item,
          blob: reader.result, // ArrayBuffer
        }
        const request = store.add(itemToStore)
        request.onerror = () => reject(request.error)
        request.onsuccess = () => {
          this.queue.push(item)
          resolve()
        }
      }
      reader.onerror = () => reject(reader.error)
      reader.readAsArrayBuffer(blob)
    })
  }
  
  async sync(): Promise<void> {
    await this.init()
    
    if (this.queue.length === 0) return
    
    const itemsToSync = [...this.queue]
    this.queue = []
    
    for (const item of itemsToSync) {
      try {
        // Reconstruct blob from ArrayBuffer if needed
        let blob = item.blob
        if (blob instanceof ArrayBuffer) {
          blob = new Blob([blob], { type: 'audio/wav' })
        }
        
        await api.saveRecording(blob, item.filename, item.gain)
        await this.removeFromIndexedDB(item.timestamp)
      } catch (error) {
        console.error('Failed to sync recording:', error)
        // Re-add to queue if sync failed
        this.queue.push(item)
      }
    }
  }
  
  private async removeFromIndexedDB(timestamp: number): Promise<void> {
    if (!this.db) return
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.delete(timestamp)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }
  
  getQueueLength(): number {
    return this.queue.length
  }
}
