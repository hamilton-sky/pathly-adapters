# Progress — hook-security-fixes

## Status

| Conversation | Title | Status |
|---|---|---|
| Conv 1 | Python security fixes and tests | DONE |
| Conv 2 | README Known Limitations | TODO |

---

## Conversation 1 — Python security fixes and tests

**Status:** DONE

**Stories:** 1, 2, 3, 4, 5

**Phases:**
- [x] Phase 1 — Locate hook scripts
- [x] Phase 2 — Hook path canonicalization
- [x] Phase 3 — Verify / add manifest traversal guard
- [x] Phase 4 — `tests/test_hooks.py`
- [x] Phase 5 — Manifest traversal test
- [x] Phase 6 — `tests/test_mcp_config.py`

**Done when:** `pytest -q` passes with all new tests collected and passing.

---

## Conversation 2 — README Known Limitations

**Status:** TODO

**Stories:** 6

**Phases:**
- [ ] Phase 1 — Verify section absent
- [ ] Phase 2 — Add Known Limitations section

**Done when:** `README.md` contains `## Known Limitations` with the four
documented items, and `pytest -q` still passes.

---

## Completion gate

Feature is complete when:
- [ ] Both conversations are marked DONE above.
- [ ] `pytest -q` passes (no skips on the new test files).
- [ ] `docs/SECURITY.md` production readiness checklist items covered by this
  feature are verifiably satisfied.
