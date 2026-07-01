# brightsky-chat-connect — Retrospective

## Cost Summary
Total: $0.95

| Agent   | Model             | Tokens in | Tokens out | Cost   | % of total |
|---------|-------------------|-----------|------------|--------|------------|
| planner | claude-sonnet-4-6 | 18,553    | 4,638      | $0.13  | 13%        |
| builder | claude-sonnet-4-6 | 121,592   | 30,398     | $0.82  | 87%        |

> Builder ran 4 passes total (2 for Conv 1 including review-fix retry, 2 for Conv 2). No reviewer or tester agent was spawned — review was inline.
> Would lite rigor have been enough? Probably not — the IPC/preload TypeScript boundary needed the review retry to catch real failures.

## Plan Quality

**Conversation sizing:** Conv 1 was well-scoped (4 stories, one clean pass + one review fix). Conv 2 was too big — 6 stories and 5 phases in one shot (WebSocket lifecycle, JWT decode/refresh, cold-start timeout, ModelSelector UI, ChatPanel routing, session ownership), requiring two builder passes. Should have been split at the WebSocket/UI boundary.

**Surprises:**
- Review found real TypeScript failures on Conv 1 (IPC/preload boundary was trickier than the plan anticipated — triggered a full retry pass)
- A `HUMAN_QUESTIONS.md` file surfaced during review, meaning the spec left ambiguities the reviewer hit
- FSM attempted TESTING after Conv 1 review passed but before Conv 2 was built — caused a GATE_FAILED and bounce back to BUILDING. The plan assumed the pipeline would wait for both convs; the FSM advanced on Conv 1 completion alone

**Missing from plan:** An explicit gate: "TESTING is blocked until both Conv 1 and Conv 2 are DONE." The plan described the conversations as sequential but didn't encode that constraint for the FSM.

## What Worked
- Clean phase structure in Conv 1 — each phase had a clear TypeScript gate, which made it easy to verify progress
- Using a Zustand `persist` store for token storage (avoids electron-store dependency) was the right call — explicitly called out in the plan
- Singleton `brightskyClient` export pattern kept the WebSocket lifecycle simple across multiple components

## What to Improve Next Time
- Split Conv 2 into Conv 2a (WebSocket client + store wiring) and Conv 2b (ModelSelector + ChatPanel UI). The WebSocket client alone is a full conversation's worth of complexity
- Add a multi-conv TESTING gate to the plan: "Enter TESTING only after all conversations are DONE" — make this explicit so the FSM doesn't advance prematurely
- Flag `HUMAN_QUESTIONS.md` ambiguities at plan-write time — the reviewer shouldn't be the first to surface spec gaps

## Seed for Next Storm
> Paste this block as context when starting the next related storm session:

brightsky-chat-connect delivered OAuth + WebSocket streaming chat integration in 2 conversations (~$0.95). The main lesson: Conv 2 was over-stuffed (WebSocket client + UI wiring together), required two builder passes, and caused the FSM to attempt premature testing. For the next BrightSky phase (sources component, AI thinking indicator, Pathly analyzer integration), split WebSocket-side work from UI-side work into separate conversations, and explicitly gate TESTING on all conversations being complete.
