# studio-arch-refactor — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | Typed service layer | Conv 1 | TODO |
| S2 | Rendering-only Sidebar | Conv 1 | TODO |
| S3 | Focused store slices | Conv 2 | TODO |
| S4 | Discriminated frontmatter union | Conv 2 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1–2 | S1, S2 | TODO | `grep -r "window\.pathly" studio/src/renderer/src/components/` → zero; `cd studio && npm run typecheck` → zero errors |
| 2 | 3–4 | S3, S4 | TODO | `cd studio && npm run typecheck` → zero errors |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 1.1 | `services/pathlyApi.ts` | CREATE service layer | All window.pathly.* calls wrapped | TODO |
| 1 | 1.2 | 9 component files | MODIFY callers | grep returns zero matches | TODO |
| 1 | 2.1 | `hooks/useProjectFiles.ts` | CREATE hook | Hook returns sections + loadItems | TODO |
| 1 | 2.2 | `hooks/usePlanConversations.ts` | CREATE hook | Hook returns planConvs | TODO |
| 1 | 2.3 | `components/Sidebar.tsx` | MODIFY to rendering-only | No async declarations remain | TODO |
| 2 | 3.1 | `store/uiStore.ts` | CREATE UI slice | useUiStore() exported | TODO |
| 2 | 3.2 | `store/projectStore.ts` | CREATE project slice | useProjectStore() exported | TODO |
| 2 | 3.3 | `store/index.ts` | MODIFY barrel | useStore() merges slices | TODO |
| 2 | 4.1 | `types/index.ts` | MODIFY add union types | FrontmatterValues is union | TODO |
| 2 | 4.2 | `Editor/ConfigForm.tsx` | MODIFY use union type | No inline type, no any casts | TODO |

## Prerequisites
- `pathly-studio` feature Convs 1–4: DONE
- Baseline typecheck passes before Conv 1 starts

## Blocked By
- Nothing
