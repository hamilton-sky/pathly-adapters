
## studio-ui-fixes — 2026-05-18

- **Parser boundary discipline**: Markdown table parsers that scan all tables pick up unintended rows. Use section heading fences (find `##` marker, break on next `##`) to scope precisely.
- **3-way null state for optional directories**: Boolean `exists/missing` is not enough when a hook can be in `not-yet-loaded` state. Use `null` = missing, `undefined` = loading, `[]` = empty-but-exists to avoid rendering empty sections prematurely.
- **Type union extension requires audit of all casts**: When adding values to a union type (`PathlyItemType`), search for `as 'old-union'` casts — they become unsafe silently and won't show TypeScript errors until narrowed downstream.
- **Duplicate pure functions across files break at divergence time**: Two identical copies of `parseProgressMd` in sibling files will silently diverge. Export the canonical version and import it everywhere.

## prod-blockers (2026-05-19)

- **Update test fixtures in the same conversation as production changes.** When adding timeout=30 or changing manifest format, the existing tests that assert on those signatures break. Fixing them post-hoc adds a feedback cycle that's avoidable.
- **Spec acceptance criteria in USER_STORIES, not just the implementation plan.** Reviewer read ARCHITECTURE_PROPOSAL and required ValueError; tester read USER_STORIES and required warn-and-return. The conflict required a correction cycle. USER_STORIES is the authoritative acceptance source.
- **Validate shared data files (manifests) against expected schema early.** marketplace.json missing `author`/`skills` caused S4.2 test scoping to be narrowed. Catching this in Conv 2 (when manifest integrity was added) would have let Conv 4 be purely assertive.
