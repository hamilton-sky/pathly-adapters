
## studio-ui-fixes — 2026-05-18

- **Parser boundary discipline**: Markdown table parsers that scan all tables pick up unintended rows. Use section heading fences (find `##` marker, break on next `##`) to scope precisely.
- **3-way null state for optional directories**: Boolean `exists/missing` is not enough when a hook can be in `not-yet-loaded` state. Use `null` = missing, `undefined` = loading, `[]` = empty-but-exists to avoid rendering empty sections prematurely.
- **Type union extension requires audit of all casts**: When adding values to a union type (`PathlyItemType`), search for `as 'old-union'` casts — they become unsafe silently and won't show TypeScript errors until narrowed downstream.
- **Duplicate pure functions across files break at divergence time**: Two identical copies of `parseProgressMd` in sibling files will silently diverge. Export the canonical version and import it everywhere.
