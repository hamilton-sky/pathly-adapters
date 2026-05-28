export interface Model {
  id: string
  name: string
  description: string
  useCase: string
  system: string
  storage: string
  speed: string
  recommended?: boolean
  /** Model emits <think>...</think> reasoning tokens — ThinkingBlock will render them */
  thinking?: boolean
  /** Ollama model tag — pass to `ollama pull` or `ollama run` */
  ollamaId: string
}

export const RECOMMENDED_MODEL_ID = 'phi-4-mini'

// IDs must match the keys in MODEL_REGISTRY in studio/src/main/ipc/llm.ts
export const WEB_LLM_MODELS: Model[] = [
  {
    id: 'qwen3-4b',
    name: 'Qwen3 4B',
    description: 'Best for Pathly — reasoning + automation planning. Emits thinking steps before answering. Strong at structured JSON output for automation flows.',
    useCase: 'Automation + general',
    system: 'CPU / GPU',
    storage: '~2.6 GB',
    speed: 'Medium',
    thinking: true,
    ollamaId: 'qwen3:4b',
  },
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
    id: 'phi-4-mini',
    name: 'Phi-4 Mini',
    description: 'Fast and light — lower memory usage with strong instruction following. No reasoning mode.',
    useCase: 'Quick responses',
    system: 'CPU / GPU',
    storage: '~2.5 GB',
    speed: 'Fast',
    recommended: true,
    ollamaId: 'phi4-mini:latest',
  },
  {
    id: 'deepseek-r1-1.5b',
    name: 'DeepSeek-R1 1.5B',
    description: 'Tiny reasoning model — shows thinking steps before answering. Best for low-RAM machines that still need reasoning capability.',
    useCase: 'Low-RAM reasoning',
    system: 'CPU / GPU',
    storage: '~1.1 GB',
    speed: 'Fastest',
    thinking: true,
    ollamaId: 'deepseek-r1:1.5b',
  },
]
