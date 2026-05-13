# Progress — docs-sync

## Conversation Map

| # | Name | Stories | Status |
|---|---|---|---|
| 1 | Fix stale claims and add missing sections | S1, S2, S3, S4, S5 | DONE |

---

## Conversation 1 — Fix stale claims and add missing sections

**Status:** DONE

**Stories delivered:** S1, S2, S3, S4, S5

**Files changed:**
- `docs/ARCHITECTURE.md`
- `docs/PATHLY_ARCHITECTURE.md`
- `docs/MULTI_TOOL_DESIGN.md`

**Tasks:**

- [x] S1a — `docs/ARCHITECTURE.md`: prefix `install_cli/materialize.py` with `src/` in tree and table
- [x] S1b — `docs/PATHLY_ARCHITECTURE.md`: prefix `install_cli/materialize.py` with `src/` in tree and table
- [x] S2  — `docs/MULTI_TOOL_DESIGN.md`: replace monorepo tree with real layout; remove `pathly-engine` rows and references
- [x] S3  — `docs/PATHLY_ARCHITECTURE.md`: update `pathly_data/` tree header and prose to `src/pathly_data/`
- [x] S4  — `docs/PATHLY_ARCHITECTURE.md`: add "Python Package Layout" section
- [x] S5  — `docs/ARCHITECTURE.md`: add `orchestrator/` scope note

**Exit checks:**
- [x] `grep -r "pathly-engine" docs/` — no results
- [x] `grep -r "install_cli/materialize" docs/` — all results include `src/` prefix
- [x] `grep "pathly_data/" docs/PATHLY_ARCHITECTURE.md` — all results include `src/` prefix
- [x] `grep -n "Python Package Layout" docs/PATHLY_ARCHITECTURE.md` — at least 1 result
- [x] `grep -n "orchestrator" docs/ARCHITECTURE.md` — new note line present
