// Shared result shape for one-shot model runs.
//
// `runModel` and every transport resolve to this. `cost_usd` is optional: local
// transports (Ollama / GGUF) are free and omit it; hosted transports may report it.

export interface RunResult {
  text: string
  cost_usd?: number
}
