# Learnings: hq-copilot

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- [review] Agent questions store options as `{id, label, description}` objects, not strings — seed fixtures the way agents post, or a crash on real data hides behind a green test.
- [review] Ollama's `/api/generate` silently truncates the START of a prompt past its default `num_ctx`; any long local-model prompt must send `options.num_ctx`.
- [review] Studio cannot call Python: a server-side prompt seam needs an HTTP route before the panel can use it.
- [review] node-llama-cpp `createModelDownloader` saves `hf_<user>_<file>.gguf` unless `fileName` is passed; Qwen3 thinking tokens are NOT streamed via onToken but DO count against maxTokens — use `budgets.thoughtTokens`.
- [review] Never render model or board text with plain `marked()` in Studio — it passes raw HTML through and the renderer can reach window.pathly; use lib/safeMarkdown.
- [review] Driving Studio over CDP while the user is using it: target HQ's textarea exactly (placeholder 'Message...'), or a test message lands in the board composer.
- [06] `activeTopic` can hold a goal-run slug, not a board; any fallback to it must check the project's feature list or the packet comes back empty.
