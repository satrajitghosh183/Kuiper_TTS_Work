import { PersistedState } from '../types/recorderState'
import { StatePersistenceManager } from './statePersistence'

export async function exportState(): Promise<string> {
  const manager = new StatePersistenceManager()
  await manager.init()
  const state = await manager.load()
  
  if (!state) {
    throw new Error('No state to export')
  }
  
  // Convert to JSON (excluding blobs)
  const exportData = {
    ...state,
    session: {
      ...state.session,
      draftBlob: state.session.draftBlob ? {
        recordingKey: state.session.draftBlob.recordingKey,
        timestamp: state.session.draftBlob.timestamp,
        // Blob excluded - user would need to re-record
      } : undefined,
    },
  }
  
  return JSON.stringify(exportData, null, 2)
}

export async function importState(json: string): Promise<void> {
  const manager = new StatePersistenceManager()
  await manager.init()
  
  const importedState: PersistedState = JSON.parse(json)
  
  // Validate and migrate
  const migratedState = {
    ...importedState,
    version: '1.0.0',
  }
  
  // Save imported state
  await manager.save(migratedState)
}
