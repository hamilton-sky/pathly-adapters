# agent-architecture-refactor — Edge Cases

## EC1 — scout-path referenced in comments or prose (not as a call instruction)

A skill file may reference `scout-path` in a historical note or explanation without it being an invocation instruction (e.g., "Previously, this stage called scout-path...").

**Handling:** The acceptance criterion for S1.1 requires that invocation instructions are replaced. Prose mentions are acceptable. The verify grep command targets the specific instruction patterns (`Call \`scout-path\``, `call **scout-path**`) rather than the raw string. Builders must read the surrounding context before replacing to confirm it is an invocation, not a comment.

---

## EC2 — team/discover.md subagents table may already be correct

If `team/discover.md` was updated in a prior refactor, the table may already describe direct spawning.

**Handling:** Builder reads the file first and confirms whether the table references scout-path as the mechanism. If already correct, Phase 6 is a no-op — the builder notes this and does not modify the file.

---

## EC3 — codex adapter may not have a tester.yaml

The scout findings confirm it exists, but if the codex adapter tester.yaml is absent, Phase 9 cannot be completed.

**Handling:** Builder reads `src/pathly_data/adapters/codex/_meta/tester.yaml` before editing. If absent, stop and report the missing file path rather than creating a new file without context.

---

## EC4 — orchestrator.md already has partial versions of the sections being added

If a prior refactor partially added git commit or PROGRESS.md logic to orchestrator.md, adding the full sections from team.md would create duplicates.

**Handling:** Builder reads orchestrator.md in full before Phase 10. If a section already exists, the builder updates/merges rather than appending a duplicate. The Done when criterion checks for content presence, not for append-only editing.

---

## EC5 — Nano mode scope confusion when converting team.md

Nano mode must stay inline in team.md. If a builder mistakenly moves nano mode to orchestrator.md, the bypass logic breaks (a user running `/team feature nano` would still reach the spawn orchestrator instruction).

**Handling:** The conversation prompt explicitly states "Nano mode remains inline in team.md." The spawn orchestrator section must be placed between mode selection and nano mode so nano is still a bypass path.

---

## EC6 — Routing table in orchestrator.md may conflict with existing subagent table

`orchestrator.md` already has a subagent spawning table (Storm → architect, Plan → planner, etc.). The team pipeline routing table (FSM states → sub-skills) is a different concept.

**Handling:** The two tables serve different purposes: the existing table maps pipeline stages to agents; the new routing table maps FSM state names to sub-skills. Builder must add the team pipeline routing table as a clearly-titled separate section, not merged into the existing subagent table.

---

## EC7 — PROGRESS.md update logic already exists in team/review.md

`team/review.md` currently marks Conv N as DONE in PROGRESS.md (line 163). After the orchestrator conversion, this responsibility moves to orchestrator.md.

**Handling:** Conv 3 (Phase 10) adds the PROGRESS.md update logic to orchestrator.md. Phase 11 removes it from team.md. The team/review.md equivalent is a separate concern (team/review.md updates during review, not after test pass) — do not modify team/review.md. If there is ambiguity about which stage should update PROGRESS.md, the builder must flag it before editing rather than guessing.
