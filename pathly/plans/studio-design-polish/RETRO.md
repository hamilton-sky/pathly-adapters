# RETRO — studio-design-polish

## 1. What went well?

**Strong token foundation & systematic refactoring.** Introduced five semantic tokens (`--font-family-base`, `--font-size-base`, `--focus-ring`, `--border`, `--transition-base`) that eliminated hardcoded values across Button, Input, IconButton, Sidebar, and FlowWizard. The dependency rule (tokens → CSS variables → components) was enforced and caught violations early (ARCH-02: `focusRing` using hex instead of `var(--accent)`; ARCH-01: `FieldError` using inline styles instead of CSS module).

**Fast decision-making on spec conflicts.** Font size resolved quickly: `15–16px` spec was de-escalated to `14px` (the existing Inter baseline at Studio) when layout impact became clear, avoiding a scope creep detour into row-height restructuring.

**Inline validation UX cohesion.** FlowWizard's error-clearing via `useEffect` pattern proved elegant — errors display on first blur/submit, clear live when the field becomes valid. The `validateStep()` pure function module kept logic testable and reusable.

**Clean ARCH violations turned into wins.** Both ARCH-02 and ARCH-01 were caught, documented, and corrected in the same phase. The review gates worked.

---

## 2. What could have gone better?

**Windows EVENTS.jsonl corruption cost debugging time.** The `echo` command malformed JSON during event logging mid-run. Detect and handle PowerShell/Bash encoding differences earlier.

**S-07 (contrast audit) blocked on tooling decision.** The story stalled waiting on architect confirmation of audit methodology. The feature shipped 6/7 stories. Clarify critical dependencies upfront — parallel-track architect decisions rather than serial-gating.

**Larger font regression risk underestimated initially.** AC-01-5 (no overflow/truncation) caught fixed-height containers clipping, requiring spot fixes. A pre-flight layout audit for font size changes would have surfaced these faster.

---

## 3. Lessons for future features

**Enforce token architecture as a structural gate.** The three-tier model (tokens → CSS variables → components) proved durable. Make it a lint rule if possible.

**De-escalate specs to scope reality early.** Cost vs. scope trade-offs should be flagged in Phase 1, not discovered mid-delivery.

**Decouple implementation from architect decisions.** If a story depends on an architect decision, implement a shim or placeholder so the feature is shippable while the decision is in flight.

**Bake accessibility into the initial token set.** Motion, contrast, and focus requirements should be in the token design from day one, not added late.

**Automate event logging validation.** Validate EVENTS.jsonl schemas immediately after recording and fail loud if the log is corrupted.

---

## Open items

- **S-07** (Light theme contrast) — blocked pending architect decision on audit tooling. Resume with `/pathly meet architect` to resolve the `ARCH_QUESTION` in STORIES.md before implementing Phase 6.
