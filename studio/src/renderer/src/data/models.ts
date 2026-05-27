export interface Model {
  id: string
  name: string
  description: string
  useCase: string
  system: string
  storage: string
  speed: string
  recommended?: boolean
  /** Ollama model tag — pass to `ollama pull` or `ollama run` */
  ollamaId: string
}

export const RECOMMENDED_MODEL_ID = 'phi-4-mini'

// IDs must match the keys in MODEL_REGISTRY in studio/src/main/ipc/llm.ts
export const WEB_LLM_MODELS: Model[] = [
  {
    id: 'qwen2.5-coder-7b',
    name: 'Qwen2.5 Coder 7B',
    description: 'Best code quality — optimized for code generation, review, and debugging tasks.',
    useCase: 'Code generation & review',
    system: 'CPU / GPU',
    storage: '~4.7 GB',
    speed: 'Slow',
    ollamaId: 'qwen2.5-coder:7b',
  },
  {
    id: 'qwen3-4b',
    name: 'Qwen3 4B',
    description: 'Balanced general-purpose model — good reasoning and instruction following.',
    useCase: 'General purpose',
    system: 'CPU / GPU',
    storage: '~2.6 GB',
    speed: 'Medium',
    ollamaId: 'qwen3:4b',
  },
  {
    id: 'phi-4-mini',
    name: 'Phi-4 Mini',
    description: 'Recommended — lower memory usage with strong instruction following capability.',
    useCase: 'Instruction following',
    system: 'CPU / GPU',
    storage: '~2.5 GB',
    speed: 'Fast',
    recommended: true,
    ollamaId: 'phi4-mini:latest',
  },
  {
    id: 'llama-3.2-3b',
    name: 'Llama 3.2 3B',
    description: 'Small fallback model — minimal memory footprint, suitable for low-spec hardware.',
    useCase: 'Low-spec fallback',
    system: 'CPU / GPU',
    storage: '~2.0 GB',
    speed: 'Fastest',
    ollamaId: 'llama3.2:3b',
  },
]
