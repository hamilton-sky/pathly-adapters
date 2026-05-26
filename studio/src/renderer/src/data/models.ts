export interface Model {
  id: string
  name: string
  description: string
  useCase: string
  system: string
  storage: string
  speed: string
  recommended?: boolean
}

export const RECOMMENDED_MODEL_ID = 'Phi-4-mini-instruct-q4f16_1-MLC'

export const WEB_LLM_MODELS: Model[] = [
  {
    id: 'Qwen2.5-Coder-7B-Instruct-q4f16_1-MLC',
    name: 'Qwen2.5 Coder 7B',
    description: 'Best code quality — optimized for code generation, review, and debugging tasks.',
    useCase: 'Code generation & review',
    system: 'WebGPU',
    storage: '~5 GB',
    speed: 'Slow',
  },
  {
    id: 'Qwen3-4B-q4f16_1-MLC',
    name: 'Qwen3 4B',
    description: 'Balanced general-purpose model — good reasoning and instruction following.',
    useCase: 'General purpose',
    system: 'WebGPU',
    storage: '~3 GB',
    speed: 'Medium',
  },
  {
    id: 'Phi-4-mini-instruct-q4f16_1-MLC',
    name: 'Phi-4 Mini',
    description: 'Recommended — lower memory usage with strong instruction following capability.',
    useCase: 'Instruction following',
    system: 'WebGPU',
    storage: '~2 GB',
    speed: 'Fast',
    recommended: true,
  },
  {
    id: 'Llama-3.2-3B-Instruct-q4f16_1-MLC',
    name: 'Llama 3.2 3B',
    description: 'Small fallback model — minimal memory footprint, suitable for low-spec hardware.',
    useCase: 'Low-spec fallback',
    system: 'WebGPU',
    storage: '~2 GB',
    speed: 'Fastest',
  },
]
