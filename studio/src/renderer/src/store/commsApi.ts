// Barrel for the comms API client.
//
// The implementation lives in ./commsApi/, one file per backend domain (split 2026-08-18 under
// the 400-line ratchet — this file was 1303 lines). This barrel exists so the 36 import sites
// across the renderer keep working unchanged: import from '../store/commsApi' as before.

export * from './commsApi/rows'
export * from './commsApi/scope'
export * from './commsApi/messages'
export * from './commsApi/artifacts'
export * from './commsApi/modelPolicy'
export * from './commsApi/runnerControl'
export * from './commsApi/search'
export * from './commsApi/boardRun'
export * from './commsApi/goalRun'
export * from './commsApi/features'
