# studio-home-redesign — Progress

## Status: IN PROGRESS

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1 | Dark mode toggle on home page | Conv 1 | TODO |
| S2 | Grid layout with view toggle | Conv 1 | TODO |
| S3 | Welcoming headline | Conv 1 | TODO |
| S4 | Richer project cards | Conv 2 | TODO |
| S5 | Pin/star favourite projects | Conv 2 | TODO |
| S6 | Improved empty state | Conv 2 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | Phase 1–3 | S1, S2, S3 | TODO | `cd studio && npm run typecheck` |
| 2 | Phase 4–7 | S4, S5, S6 | TODO | `cd studio && npm run typecheck` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Phase 1 | `studio/src/renderer/src/types/index.ts` | Add `pinned?: boolean` to ProjectEntry | Type compiles without new errors | TODO |
| 1 | Phase 2 | `studio/src/renderer/src/components/HomeScreen.tsx` | Dark mode + view toggle in drag strip | Toggle buttons render and work | TODO |
| 1 | Phase 3 | `studio/src/renderer/src/components/HomeScreen.tsx` | Welcome subtitle + grid layout | Grid renders, subtitle visible | TODO |
| 2 | Phase 4 | `studio/src/renderer/src/components/HomeScreen.tsx` | Top accent border + hover glow | Cards color-coded by state | TODO |
| 2 | Phase 5 | `studio/src/renderer/src/components/HomeScreen.tsx` | Footer row with topic count + Open button | Footer visible with correct data | TODO |
| 2 | Phase 6 | `studio/src/renderer/src/components/HomeScreen.tsx` | Pin/star toggle and pinned section | Pinned projects float to top | TODO |
| 2 | Phase 7 | `studio/src/renderer/src/components/HomeScreen.tsx` | Improved empty state | FolderOpen icon + labels shown when no projects | TODO |

## Prerequisites
- PO_NOTES.md and DESIGN.md already written in this folder
- Read DESIGN.md for full visual spec before starting Conv 2

## Blocked By
- Nothing
