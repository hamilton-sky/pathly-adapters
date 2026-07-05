# connectors-rename — rename the "fragments" connection layer to "connectors"

**Status:** SPEC (deferred, board-homed) · **Date:** 2026-07-05

## Why

"Fragments" names a *shape* (a snippet of text), not a *responsibility*. The layer's actual job is
**how every agent connects to Pathly**: the un-editable system-prompt block that owns all board CRUD,
context retrieval, progress logging, and completion. Renaming it to **connectors** makes the concept
self-describing — a reader sees "connectors/" and knows this is the connection-to-Pathly layer, not
"some editable prose."

Candidate names considered: **connectors** (recommended), bridge, runtime, harness, conduit, spine.
Confirm the name before starting — it's cheap to change now, expensive after the rename lands.

## Scope (grounded 2026-07-05, live code only — archives + historical docs excluded)

| Surface | Refs / files | Load-bearing spots |
|---|---|---|
| Python `src/pathly_orchestrator` | 139 / 16 | `skills/compose.py` (37), `blueprints/skills/editor_render.py` (27), `blueprints/catalog/items.py` (17), `db/queries/catalog_indexers.py` (10), `db/queries/skill_composition.py` (10), `catalog.py` (7), `skills/__init__.py` (6), `editor_io.py` (6) |
| Data `src/pathly_data/core` | 63 / 16 | `skills/composition.yaml` (**45** — the `fragments:` spec keys + `fragments_dir`), the **`skills/fragments/` directory itself**, skill bodies |
| Studio `studio/src` | 115 / 25 | `FlowWizard/BlockAuthorForm` (24), `MarkdownEditor/markdownEditorStore` (16), `EditorCanvas` (13), `LibraryCatalog/ItemRow` (9), `CatalogPanel/FragmentCard`, `MarkdownEditor/FragmentCell` |
| **DB data value** | rows | `item_type='fragment'` in `catalog_items` + `skill_composition` — **stored data, needs a migration or dual-read**, not just code |
| Tests | — | `test_compose.py` (12), golden snapshots |
| Docs | — | `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/PATHLY_ARCHITECTURE.md`, `README` |

**Total ~317 live references across ~57 files** + a DB value + a directory + 4 installed host copies.
This is why it is its own focused pass, not a sed sweep.

## The one real gotcha

`item_type='fragment'` is a **value stored in the DB** (`catalog_items`, `skill_composition`), and
`fragments_dir`/`fragments:` are keys in `composition.yaml`. A pure code rename that ignores stored
data would make already-indexed rows invisible. So the rename needs **dual-read compatibility**
during the transition, not a big-bang find-replace.

## Approach — de-risked, phased (never big-bang)

- **C1 — alias in, both accepted.** Compose loader reads both `connectors:`/`fragments:` and
  `fragments_dir` probes `connectors/` then `fragments/`. DB reads accept `item_type IN
  ('connector','fragment')`. No behavior change; both names work.
- **C2 — rename on disk.** `core/skills/fragments/` → `core/skills/connectors/`; flip
  `composition.yaml` keys to `connectors:`. Alias from C1 keeps old data valid.
- **C3 — DB migration.** `UPDATE … SET item_type='connector' WHERE item_type='fragment'` (+
  `skill_composition`); reindex. Backup first (one txn).
- **C4 — Studio.** Rename `FragmentCell`→`ConnectorCell`, `FragmentCard`→`ConnectorCard`, store
  keys, labels, tokens. Biggest surface (25 files) — do behind the C1 alias so nothing breaks mid-flight.
- **C5 — finish.** Docs, `pathly-setup <host> --apply --repair` for all 4 adapters, then drop the
  aliases. Reserved-name set / discovery updated last.

## Invariant (load-bearing)

**Composed prompts must be byte-identical before and after every phase** — the rename is cosmetic to
the *output*; only names change. Guard with the existing golden-snapshot compose tests: regenerate,
diff must be empty except for the term itself where it appears in prompt text (verify none does, or
update snapshots deliberately).

## Relationship

Independent of [board-scoped-storage]. Same discipline as any cross-cutting rename in this repo:
alias-first, dual-read, golden-snapshot guard, adapters rebuilt last.
