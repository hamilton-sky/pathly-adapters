---
name: Conversation Guide
---
# Comms Board — Studio CommsPanel (Phase 2) — Conversation Guide

Split into 3 conversations (max 4). Each ends typecheck-clean. Commit after each (when the
human asks — do NOT auto-commit/push; the orchestrator gates commits).

---

## Conversation 1: Store + API + SSE wiring (Phases 1–3)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Read pathly/plans/comms-board-studio/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Studio Conversation 1 (Phases 1–3) from
pathly/plans/comms-board-studio/IMPLEMENTATION_PLAN.md.

This is the Studio frontend for the Phase 1 comms backend (already on master): the endpoints
POST /comms/post, GET /comms, POST /comms/search, POST /comms/answer, POST /comms/acknowledge,
and SSE GET /events/comms?scope=<feature>. Convention: board ∈ {feature,project,global},
scope = identifier (feature name / project root / 'global').

**Before editing:** glob/read to confirm paths. Study these for patterns:
- store/chatStore.ts (Zustand create<...>() + actions shape)
- components/HQ/useHQ.tsx — the existing /events/runner EventSource effect and the
  handleAgentAnswer fetch pattern (raw fetch to 127.0.0.1:8765, errors .catch'd)
- store/notificationStore.ts — NotifCategory + DEFAULT_CATEGORIES (already has 'phase_summary')
- store/index.ts — how stores are re-exported

Scope:
- Phase 1: create store/commsStore.ts — CommsMessage interface + state (messages, board, scope,
  pendingCount, loading) + actions (appendMessage [dedup by id], setMessages, markRead, setBoard, clear).
- Phase 2: create services/commsApi.ts — postMessage/getMessages/searchMessages/answerQuestion/
  acknowledgeMessage as raw fetch wrappers; all errors .catch → return {ok:false}. Map the board
  toggle to params: feature→scope=feature, project→scope=projectRoot, global→scope='global'.
- Phase 3: modify components/HQ/useHQ.tsx — add a useEffect keyed on the active topic that calls
  commsApi.getMessages → setMessages, opens a SECOND EventSource to
  /events/comms?scope=<activeTopic>, appends COMMS_UPDATE messages to commsStore, and closes the
  EventSource on cleanup. Add 'comms_update' to NotifCategory + DEFAULT_CATEGORIES. Re-export
  useCommsStore from store/index.ts.

Studio rules (read studio/CLAUDE.md): no inline styles (none needed this conv); strict TS; do not
break the existing /events/runner effect — add a separate effect, don't merge.

Do NOT touch: any CommsPanel component (Conv 2), any Python file, any adapter file.
Verify: node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json passes; then manually start
pathly-fsm-http, set an active feature, curl POST a message to that feature, and confirm it lands
in commsStore (React devtools or a temporary console.log you remove before finishing).
After done, update pathly/plans/comms-board-studio/PROGRESS.md phases 1–3 to DONE. Do NOT commit.

If verification fails and the fix needs out-of-scope changes, stop and report.
```

**Expected output:** `commsStore` + `commsApi` exist and typecheck; the active feature's board
loads and updates live via SSE. No visible UI yet.
**Files touched:** `store/commsStore.ts`, `store/index.ts`, `services/commsApi.ts`, `store/notificationStore.ts`, `components/HQ/useHQ.tsx`

---

## Conversation 2: CommsPanel shell + message thread (Phases 4–7)

**Stories delivered:** S2.1, S2.2

**Prompt to paste:**
```
Read pathly/plans/comms-board-studio/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Studio Conversation 2 (Phases 4–7) from
pathly/plans/comms-board-studio/IMPLEMENTATION_PLAN.md.
Conversation 1 is complete: commsStore, commsApi, and the /events/comms SSE wiring exist.

Design guidance — read pathly/plans/comms-board/CONSULTATION.md §3 (designer):
- board selector is PILL/CHIP TOGGLES, not tabs (§3.2)
- panel subtitle: "Agents read this at the start of each stage"
- decisions are pinned at the top with 📌

**Before editing:** glob/read. Study components/HQ/AgentQuestionCard/ (card structure + CSS module
data-attribute pattern) and components/HQ/index.tsx (where docked cards mount in panelInner).

Scope (one component + its .module.css per folder; keep each < 150 lines):
- Phase 4: CommsPanel/CommsMsgCard.tsx — props {msg}; root carries data-type={msg.type}; CSS module
  styles each variant (status/decision/nudge/warning/discovery/answer). 📌 marker on decision.
- Phase 5: CommsPanel/CommsMsgList.tsx — props {messages}; pin decisions at top then the rest;
  empty-state element when no messages.
- Phase 6: CommsPanel/CommsPanel.tsx + CommsPanel/hooks/useCommsPanel.ts — shell (header+subtitle,
  BoardToggle slot, CommsMsgList, an empty send-bar slot for Conv 3); useCommsPanel holds UI state
  (active board + filtered messages from commsStore). Mount <CommsPanel/> in components/HQ/index.tsx
  AFTER <AgentQuestionCard> (~line 39), shown when there is an active topic.
- Phase 7: CommsPanel/BoardToggle.tsx — pill toggles Feature/Project/Global; active pill via
  data-active; on select call commsApi.getMessages with the mapped board/scope and setMessages/setBoard.

Studio rules (studio/CLAUDE.md): NO inline styles — all styling in .module.css using var(--*) tokens;
data-* attributes for the 3+ message-type variants; every <button> type="button"; ARIA (aria-pressed
on pills). Extract anything over ~150 lines.

Do NOT touch: Conv 1 files except to import them; CommsInput/CommsQuestionCard (Conv 3); any Python file.
Verify: node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json passes; then run Studio, select a
feature with board messages (post a few via curl), confirm the panel shows them with decisions pinned
and the board toggle switches scope.
After done, update PROGRESS.md phases 4–7 to DONE. Do NOT commit.

If verification fails and the fix needs out-of-scope changes, stop and report.
```

**Expected output:** A docked CommsPanel shows the active feature's board live, decisions pinned,
with working Feature/Project/Global pill toggles. Read-only (no compose yet).
**Files touched:** `CommsPanel/CommsMsgCard.tsx`, `CommsMsgList.tsx`, `CommsPanel.tsx`, `hooks/useCommsPanel.ts`, `BoardToggle.tsx` (+ CSS modules), `components/HQ/index.tsx`

---

## Conversation 3: Compose + interactions (Phases 8–10)

**Stories delivered:** S3.1, S3.2

**Prompt to paste:**
```
Read pathly/plans/comms-board-studio/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Studio Conversation 3 (Phases 8–10) from
pathly/plans/comms-board-studio/IMPLEMENTATION_PLAN.md.
Conversations 1–2 are complete: the store/API/SSE and the read-only CommsPanel + BoardToggle exist.

Design guidance — pathly/plans/comms-board/CONSULTATION.md §3.3–3.4 (designer):
- compose: type selector DEFAULTS to "Note", changed AFTER writing; offer Decision / Task / Note / Question
  (Attach is deferred — the backend /comms/attach is a 501 stub)
- escalation messages get a distinct red banner

**Before editing:** glob/read. Reuse the components/HQ/AgentQuestionCard/ structure for the question card.

Scope (one component + .module.css per folder; < 150 lines each):
- Phase 8: CommsPanel/CommsInput.tsx — textarea + type dropdown (default Note: Decision/Task/Note/Question);
  Send → commsApi.postMessage({feature, board, type, text, from:'human'}); optimistic append (reconciled
  by the SSE echo; dedup by id); Send disabled on empty text. Fill the send slot in CommsPanel.tsx.
- Phase 9: CommsPanel/CommsQuestionCard.tsx — for type==='question': render msg.options as type="button"
  option buttons (reuse AgentQuestionCard pattern); click → commsApi.answerQuestion({question_id: msg.id,
  answer, option_id}); show "answered" until status flips resolved via SSE. Wire it into the list/card for
  question-type messages.
- Phase 10: CommsPanel/CommsMsgCard.tsx (modify) — type==='warning' gets an Acknowledge button →
  commsApi.acknowledgeMessage; type==='escalation' renders a red banner variant (data-type='escalation').
  If CommsMsgCard exceeds ~150 lines, extract the banner into its own sub-component + module.

Studio rules (studio/CLAUDE.md): NO inline styles; data-* for variants; every <button> type="button";
ARIA labels on interactive elements; tokens from tokens.css.

Do NOT touch: any Python file, any adapter file. Keep changes within CommsPanel/.
Verify: node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json passes; then run Studio: post a Note
from the compose bar (appears), post a question via curl and answer it from the UI (resolves), post an
escalation via curl (red banner), acknowledge a warning.
After done, update PROGRESS.md phases 8–10 to DONE and Status to COMPLETE. Do NOT commit.

If verification fails and the fix needs out-of-scope changes, stop and report.
```

**Expected output:** Full single-feature CommsPanel — read, post, answer questions, acknowledge
warnings, and see escalations. Phase 2 complete.
**Files touched:** `CommsPanel/CommsInput.tsx`, `CommsQuestionCard.tsx`, `CommsMsgCard.tsx` (+ CSS modules), `CommsPanel.tsx`
