# Feature Index — unified-ai-routing

Unify Studio AI dispatch into three single-responsibility pieces (CLI Engine, AI Model
Manager, Router) and route board-artifact summaries through the Router — retiring the
broken server-side summarizer.

| File | Purpose |
|---|---|
| `PO_NOTES.md` | Requirements brief (problem, target design, hard requirements, cleanup) |
| `STORM_SEED.md` | Technical storm — component contracts, transports, triggers, risks |
| `ARCHITECTURE_PROPOSAL.md` | Cross-layer component + interface contract |
| `FLOW_DIAGRAM.md` | Dispatch + summary-trigger flows |
| `USER_STORIES.md` | US-1…US-5 with acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Conversations 1–5 |
| `CONVERSATION_PROMPTS.md` | Per-conversation builder prompts |
| `PROGRESS.md` | Status table |

**Rigor:** standard · **Mode:** fast/auto-flow · **Layers:** Python + Studio
**Hard constraint:** no Anthropic API key; cleanup of old summarizer is an acceptance criterion.
