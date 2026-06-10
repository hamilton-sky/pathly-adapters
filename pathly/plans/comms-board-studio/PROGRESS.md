---
name: Progress
---
# Comms Board — Studio CommsPanel (Phase 2) — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Comms store + API client | Conv 1 | TODO |
| S1.2 | Live board updates over SSE | Conv 1 | TODO |
| S2.1 | See the board — message thread | Conv 2 | TODO |
| S2.2 | Switch board scope | Conv 2 | TODO |
| S3.1 | Post to the board | Conv 3 | TODO |
| S3.2 | Answer questions, acknowledge, escalations | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1–3 | S1.1, S1.2 | TODO | `tsc --noEmit -p studio/tsconfig.web.json` + curl post appears in store |
| 2 | 4–7 | S2.1, S2.2 | TODO | typecheck + panel shows live messages, toggle switches board |
| 3 | 8–10 | S3.1, S3.2 | TODO | typecheck + post/answer/escalation work from the UI |

See **CONVERSATION_PROMPTS.md** for exact prompts.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1 commsStore | `store/commsStore.ts` | Zustand store + actions | appendMessage dedups by id | TODO |
| 1 | 2 commsApi | `services/commsApi.ts` | fetch wrappers /comms/* | calls resolve without throwing | TODO |
| 1 | 3 SSE wiring | `components/HQ/useHQ.tsx` | 2nd EventSource + initial load | curl post appears in store | TODO |
| 2 | 4 CommsMsgCard | `CommsPanel/CommsMsgCard.tsx` | message card, data-type | variant renders, 📌 on decision | TODO |
| 2 | 5 CommsMsgList | `CommsPanel/CommsMsgList.tsx` | thread, pinned decisions | decisions pinned top | TODO |
| 2 | 6 CommsPanel + mount | `CommsPanel/CommsPanel.tsx` + `HQ/index.tsx` | shell + dock in HQ | panel visible w/ live messages | TODO |
| 2 | 7 BoardToggle | `CommsPanel/BoardToggle.tsx` | pill toggles | toggle switches board | TODO |
| 3 | 8 CommsInput | `CommsPanel/CommsInput.tsx` | compose + type dropdown | post Note → appears | TODO |
| 3 | 9 CommsQuestionCard | `CommsPanel/CommsQuestionCard.tsx` | question + options | answer from UI resolves | TODO |
| 3 | 10 warnings/escalation | `CommsPanel/CommsMsgCard.tsx` | ack + red banner | escalation red banner | TODO |

## Prerequisites
- Phase 1 backend on master (shipped); `pathly-fsm-http` running for manual checks
- Studio builds today; `npm i` done

## Blocked By
- Nothing
