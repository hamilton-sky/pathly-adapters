# simplify-review — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1.1 | Cross-reference deduplication (ARCHITECTURE.md, PATHLY_ARCHITECTURE.md) | Conv 1 | TODO |
| S1.2 | README clarity and correctness | Conv 1 | TODO |
| S1.3 | FLOW_DIAGRAM.md completeness and Copilot coverage | Conv 1 | TODO |
| S1.4 | PATHLY_ARCHITECTURE.md structural fixes | Conv 1 | TODO |
| S2.1 | Schema sync and enrichment | Conv 2 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1–3 | S1.1, S1.2, S1.3, S1.4 | TODO | `git diff --stat HEAD` (doc files only) |
| 2 | 4 | S2.1 | TODO | `git diff --stat HEAD` (schema files only) |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 1 | `docs/ARCHITECTURE.md` | Remove "20" count; replace skill table with FLOW_DIAGRAM.md link | No duplicate skill table; no hardcoded count | TODO |
| 1 | 1 | `docs/PATHLY_ARCHITECTURE.md` | Scope note; tree fix; team-flow comment; annotation style; pip fix | Scope note present; tree clean; entry-point annotated | TODO |
| 1 | 2 | `README.md` | Trim quick-start; equivalence note; hosts table; meta path; Copilot row | ≤4 commands; equivalence note present; paths correct | TODO |
| 1 | 3 | `docs/FLOW_DIAGRAM.md` | Complete prose; verify footnote; Copilot mermaid branch; Copilot examples | No trailing "…"; footnote present; Copilot in diagram | TODO |
| 2 | 4 | `schemas/pathly-meta.schema.json` | Add missing properties + constraints + descriptions | All properties present; enum values set | TODO |
| 2 | 4 | `src/pathly_data/schemas/pathly-meta.schema.json` | Sync with root + add required/enum/minLength/description | Files are in sync; all constraints present | TODO |

## Prerequisites
- Clean working tree before Conversation 1

## Blocked By
- Nothing
