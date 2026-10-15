// Answer text from the built-in runtime. Qwen3's reasoning arrives as node-llama-cpp
// "thought" SEGMENTS (llm.ts wraps them in <think>…</think> itself); a literal think tag in
// the plain answer is the model misfiring — measured in-app: after a function call it ended
// its answer with a bare "</think>", which rendered as text. Strip them from answer text.
export function stripThinkTags(text: string): string {
  return text.replace(/<\/?think>/g, '')
}
