# Progress — po-planner-separation

## Status

| Conversation | Title | Status |
|---|---|---|
| Conv 1 | PO agent + team-flow plan pipeline | NOT STARTED |
| Conv 2 | Planner + tester escalation protocols | NOT STARTED |

---

## Conversation 1 — PO agent + team-flow plan pipeline

**Status:** NOT STARTED

**Stories:** 1, 2

**Phases:**
- [ ] Phase 1 — Pre-flight read
- [ ] Phase 2 — Update po.md
- [ ] Phase 3 — Update plan.md Stage 2

**Done when:**
- `po.md` contains a subsection describing three activation cases and a
  three-row fallback table.
- `plan.md` Stage 2 contains a "PO Phase" section before "Phase 1 — Analyze".
- Phase 3 planner prompt in `plan.md` references `PO_NOTES.md` as authoritative
  source.
- All existing content in both files is preserved verbatim.

---

## Conversation 2 — Planner + tester escalation protocols

**Status:** NOT STARTED

**Stories:** 3, 4

**Phases:**
- [ ] Phase 1 — Pre-flight read
- [ ] Phase 2 — Update planner.md
- [ ] Phase 3 — Update tester.md

**Done when:**
- `planner.md` contains an "Escalation protocols during decomposition" section
  with all three paths (PO advisory spawn / OPEN halt / ARCH_QUESTION).
- `tester.md` "What NOT to do" contains an ARCH_QUESTION escalation bullet.
- All existing content in both files is preserved verbatim.

---

## Completion gate

Feature is complete when:
- [ ] Both conversations are marked DONE above.
- [ ] All four acceptance criteria tables in USER_STORIES.md are fully checked.
- [ ] No existing section in any of the four target files has been removed or
  reworded outside the planned additions.
