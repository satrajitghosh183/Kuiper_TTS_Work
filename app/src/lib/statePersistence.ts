import { PersistedState } from '../types/recorderState'
import { supabase, getCurrentUser, isSupabaseConfigured } from './supabase'

const DB_NAME = 'kuiper-recorder-state'
const STORE_NAME = 'state'
const STATE_KEY = 'current-session'
const VERSION = '1.0.0'

export class StatePersistenceManager {
  private db: IDBDatabase | null = null
  
  async init(): Promise<void> {
    if (this.db) return
    
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        resolve()
      }
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME)
        }
      }
    })
  }
  
  async save(state: PersistedState): Promise<void> {
    // Save to IndexedDB (local, fast)
    await this.saveToIndexedDB(state)
    
    // Also sync to Supabase (cloud, cross-device) if configured
    if (isSupabaseConfigured() && await this.isOnline()) {
      try {
        await this.saveToSupabase(state)
      } catch (error) {
        console.warn('Failed to save state to Supabase (continuing with local save):', error)
      }
    }
  }
  
  private async saveToIndexedDB(state: PersistedState): Promise<void> {
    if (!this.db) await this.init()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      
      // Convert Blob to ArrayBuffer for storage
      const stateToSave = {
        ...state,
        session: {
          ...state.session,
          draftBlob: state.session.draftBlob ? {
            ...state.session.draftBlob,
            blob: null, // Will be stored separately
            blobId: state.session.draftBlob.recordingKey,
          } : undefined,
        },
      }
      
      const request = store.put(stateToSave, STATE_KEY)
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        // Save draft blob separately if exists
        if (state.session.draftBlob) {
          this.saveBlobToIndexedDB(
            state.session.draftBlob.recordingKey,
            state.session.draftBlob.blob
          ).then(resolve).catch(reject)
        } else {
          resolve()
        }
      }
    })
  }
  
  private async saveBlobToIndexedDB(key: string, blob: Blob): Promise<void> {
    if (!this.db) await this.init()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      
      const reader = new FileReader()
      reader.onload = () => {
        const request = store.put(reader.result, `blob-${key}`)
        request.onerror = () => reject(request.error)
        request.onsuccess = () => resolve()
      }
      reader.onerror = () => reject(reader.error)
      reader.readAsArrayBuffer(blob)
    })
  }
  
  private async saveToSupabase(state: PersistedState): Promise<void> {
    if (!isSupabaseConfigured() || !supabase) return
    
    try {
      const user = await getCurrentUser()
      if (!user) return // Not authenticated
      
      // Save session state to Supabase recording_sessions table
      const scriptId = state.scripts[state.session.currentScriptIndex]?.name || null
      
      const { error } = await supabase
        .from('recording_sessions')
        .upsert({
          user_id: user.id,
          script_id: scriptId,
          current_line_index: state.session.currentLineIndex,
          draft_blob_url: state.session.draftBlob 
            ? await this.uploadDraftBlob(state.session.draftBlob.blob)
            : null,
          updated_at: new Date().toISOString(),
        }, {
          onConflict: 'user_id,script_id'
        })
      
      if (error) throw error
    } catch (error) {
      console.error('Failed to save state to Supabase:', error)
      // Don't throw - local save succeeded
    }
  }
  
  private async uploadDraftBlob(blob: Blob): Promise<string | null> {
    if (!isSupabaseConfigured() || !supabase) return null
    
    try {
      const user = await getCurrentUser()
      if (!user) return null
      
      const filename = `draft-${Date.now()}.wav`
      const { data, error } = await supabase.storage
        .from('drafts')
        .upload(`${user.id}/${filename}`, blob, {
          contentType: 'audio/wav',
          upsert: true,
        })
      
      if (error) throw error
      return data.path
    } catch (error) {
      console.error('Failed to upload draft blob:', error)
      return null
    }
  }
  
  async load(): Promise<PersistedState | null> {
    // Try Supabase first (most recent), fallback to IndexedDB
    if (isSupabaseConfigured()) {
      const supabaseState = await this.loadFromSupabase()
      if (supabaseState) return supabaseState
    }
    
    return await this.loadFromIndexedDB()
  }
  
  private async loadFromIndexedDB(): Promise<PersistedState | null> {
    if (!this.db) await this.init()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.get(STATE_KEY)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        const state = request.result
        if (!state) {
          resolve(null)
          return
        }
        
        // Restore draft blob if exists
        if (state.session?.draftBlob?.blobId) {
          this.loadBlobFromIndexedDB(state.session.draftBlob.blobId)
            .then((blob) => {
              if (blob) {
                state.session.draftBlob = {
                  ...state.session.draftBlob,
                  blob,
                }
              }
              resolve(this.migrateState(state))
            })
            .catch(reject)
        } else {
          resolve(this.migrateState(state))
        }
      }
    })
  }
  
  private async loadBlobFromIndexedDB(key: string): Promise<Blob | null> {
    if (!this.db) await this.init()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readonly')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.get(`blob-${key}`)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        const arrayBuffer = request.result
        if (!arrayBuffer) {
          resolve(null)
          return
        }
        resolve(new Blob([arrayBuffer], { type: 'audio/wav' }))
      }
    })
  }
  
  private async loadFromSupabase(): Promise<PersistedState | null> {
    if (!isSupabaseConfigured() || !supabase) return null
    
    try {
      const user = await getCurrentUser()
      if (!user) return null
      
      const { data, error } = await supabase
        .from('recording_sessions')
        .select('*')
        .eq('user_id', user.id)
        .single()
      
      if (error || !data) return null
      
      // Reconstruct state from Supabase data
      // Note: This is a simplified version - full implementation would need
      // to reconstruct scripts and recordings from Supabase
      return null // Placeholder - would need full Supabase schema implementation
    } catch (error) {
      console.error('Failed to load state from Supabase:', error)
      return null
    }
  }
  
  private migrateState(state: any): PersistedState {
    // Handle state version migrations
    if (state.version !== VERSION) {
      // Migrate old state format to new format
      return {
        ...state,
        version: VERSION,
      }
    }
    return state
  }
  
  async clear(): Promise<void> {
    if (!this.db) await this.init()
    
    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)
      const request = store.delete(STATE_KEY)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => resolve()
    })
  }
  
  private async isOnline(): Promise<boolean> {
    return navigator.onLine
  }
}
