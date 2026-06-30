# REVIEW_FAILURES.md — md-diagram-conversion (Phase 7 Code Review)

**Reviewer:** Claude Code (manual, read-only) · **Date:** 2026-06-30
**Scope:** the copied implementation under `studio/src/renderer/src/components/MarkdownEditor/` + 3 patched files.
**Source of truth:** `md-diagram-feature/` as-built; `ARCHITECTURE_PROPOSAL.md` treated as partially superseded.

## Verdict

**Implementation is sound and both typecheck gates are clean.** No functional/security blockers.
Findings below are **3 real rule violations** (inline styles ×2 sites, one story-text mismatch) plus
**4 advisories** (file length, dangling comment, an architectural divergence to adjudicate, a folder-convention nit).
Nothing here blocks Phase 8, but R1–R3 should be fixed before the feature is considered done.

---

## Violations

### R1 — [MEDIUM] Inline `style={{}}` for enum-driven colour — violates the non-negotiable "No inline styles" rule
`studio/CLAUDE.md` → *UI coding rules → No inline styles* forbids `style={{}}` for presentation and
prescribes the `data-*` variant pattern for enum-driven colours.

- `DiagramGalleryPanel/DiagramCard/DiagramCard.tsx:33` — `style={{ color: styleColor }}`
- `DiagramGalleryPanel/DiagramCard/DiagramCard.tsx:34` — `style={{ background: styleColor }}`

`styleColor` = `STYLE_COLOR_VAR[entry.style]` (`var(--blue)` / `var(--yellow)` / `var(--purple)`).
Setting the standard `color`/`background` properties inline is the banned form — this is **not** the
sanctioned custom-property carrier exception.
**Fix:** drop `STYLE_COLOR_VAR` from the TSX; add `<span className={styles.badge} data-style={entry.style}>`
(+ `data-style` on the dot) and move the hue mapping into `DiagramCard.module.css`:
`.badge[data-style='mermaid']{color:var(--blue)} .badge[data-style='ascii']{color:var(--yellow)} .badge[data-style='plantuml']{color:var(--purple)}`.

### R2 — [✅ RESOLVED 2026-06-30] Lightbox transform now uses a CSS custom-property carrier
- `DiagramLightbox.tsx` stage now sets `style={{ '--tx', '--ty', '--zoom' } as React.CSSProperties}` and
  `.stage` in the CSS module applies `transform: translate(var(--tx), var(--ty)) scale(var(--zoom))`.
- Fixed as part of the lightbox UX pass (dot-grid → soft gray, fit-to-viewport, MAX_ZOOM 4→8, action toolbar).
  Renderer typecheck clean.

### R3 — [LOW-MEDIUM] PlantUML notice text does not match its story contract
- `DiagramGalleryPanel/DiagramRender/DiagramRender.tsx:43` renders
  `"PlantUML render engine not bundled yet — showing source"` **above** the `<pre>`.
- `USER_STORIES.md` S-07 requires the EXACT text `"PlantUML render engine not bundled. Paste source into
  plantuml.com to render."` **below** the source.

Note: the spec is internally inconsistent — `FEATURE_INDEX.md` D6 only says a "render engine not bundled yet"
notice (which the code matches). **Action for product:** pick one wording. As-is, S-07's literal acceptance
will FAIL in Phase 8; either relax S-07 to match FEATURE_INDEX, or update the notice string + position.

---

## Advisories (record, not blocking)

### R4 — [LOW] File-length budget exceeded (expected per task brief)
- `EditorHeader/hooks/useEditorDiagramAction.ts` — **174 lines** (renderer budget ≤150). Extract the
  `onExit` completion handler (poll → success/error branch, lines ~112–137) into a helper to get under budget.
- `EditorHeader/EditorHeader.tsx` — **550 lines** (over the 400 hard cap; pre-existing, +~114 from this feature).
  The three `ActionPill` blocks + their peek/preview/once-prompt state are extractable. **Recommend a follow-up
  split**, out of scope for this feature.

### R5 — [LOW] Dangling `STORE_PATCH.md` references in shipped source
- `EditorHeader/hooks/useEditorDiagramAction.ts:7` and `DiagramGalleryPanel/diagramSidecar.ts` header comments
  point at `STORE_PATCH.md`, which was (correctly) not copied into source. Update/drop the comment so it doesn't
  send a reader to a non-existent file.

### R6 — [ADVISORY] Architectural divergence — Diagram prompts bypass fragment composition
- `useEditorDiagramAction.ts:17,47–55` resolves prompts via `resolvePrompt` over `DIAGRAM_PRESETS`, **not**
  `composeClientSkill` as `ARCHITECTURE_PROPOSAL.md` §5 promised. Consequence: Diagram prompts are **not
  fragment-composed**, in tension with the repo's "every prompt Pathly sends to a CLI should flow through
  fragments" direction (root `CLAUDE.md`).
- **To adjudicate:** check whether the Split/Analyze siblings (`useEditorAgentActions.ts`) also bypass fragments.
  If they do, this is consistent and the arch doc is simply stale; if they compose, Diagram is the outlier and
  should be brought in line. Either way, not a code defect — a product/architecture decision.

### R7 — [ADVISORY] Folder-convention nit — `MermaidView.tsx` has no own subfolder
- `DiagramGalleryPanel/DiagramRender/MermaidView.tsx` shares `DiagramRender.module.css` and has no
  `MermaidView/` subfolder. `studio/CLAUDE.md`'s folder rule ("no exceptions for small components") would put it
  at `DiagramRender/MermaidView/MermaidView.tsx`. It's a tightly-coupled sub-renderer with no styles of its own —
  low priority, note only.

---

## Confirmed clean (checked, no violation)

- **Mermaid safety:** `securityLevel:'strict'`; lazy `import('mermaid')` + module-scope cache; theme dep +
  `active`-flag unmount guard; `mermaid.render` error → `<pre>` fallback (never crashes the card). The only
  `dangerouslySetInnerHTML` in the feature is `MermaidView.tsx:92` (mermaid-sanitized SVG only).
- **Hex literals:** none outside the 7 `tokenValue(cs,'--x','#fallback')` fallbacks in `MermaidView.tsx`
  (reconciled rule). All `.module.css` files are token-only — zero hex.
- **Buttons:** every `<button>` carries `type="button"` (DiagramCard 4/4, DiagramLightbox 2/2, panel header/empty-CTA).
- **Lazy store access:** all store reads in callbacks/effects use `useUiStore.getState()` /
  `useTerminalStore.getState()` — no stale-closure capture (`useEditorDiagramAction.ts:79,87,99,116,144,163`).
- **Run-guard:** `useEditorDiagramAction.ts:99` early-returns when the file's diagram slot is `running` — one
  in-flight run per file; holds even across the two hook instances (header + `DiagramGalleryPanel.tsx:52`) because
  the guard reads shared store state.
- **Sidecar I/O:** `isValidSidecar` guard, empty-on-missing/parse-fail, malformed-entry filter, last-delete
  deletes the file; renderer never appends (agent-owns-append contract honored).
- **Schema:** `diagramTypes.ts` pins `DiagramEntry`/`DiagramSidecar` (version:1) — closes the
  schema-underspecification gap flagged in `ARCHITECTURE_PROPOSAL.md.analysis`.
- **Header wiring:** 3rd `ActionPill` + `pendingRun.kind:'diagram'` → `SendPreviewModal` → `handleDiagram`;
  `PromptPeekModal` via `DIAGRAM_PRESETS`; CLI/preset persisted to localStorage. Complete.

---

## Resolution status (updated 2026-06-30)

| # | Sev | Status |
|---|---|---|
| R1 | MED | ✅ Resolved — badge uses `data-style={entry.style}` + `.badge[data-style=…]` hue rules in `DiagramCard.module.css`; dot inherits via `currentColor`; `STYLE_COLOR_VAR` removed from `diagramTypes.ts`. No inline style. |
| R2 | LOW-MED | ✅ Resolved — pan/zoom via `--tx/--ty/--zoom` custom properties (lightbox UX pass). |
| R3 | LOW-MED | ✅ Resolved — notice now uses S-07's exact text, below the source ("PlantUML render engine not bundled. Paste source into plantuml.com to render."). |
| R4 | LOW | ◻ Advisory — file lengths (`useEditorDiagramAction.ts` ~174; `EditorHeader.tsx` ~550). Follow-up split. |
| R5 | LOW | ✅ Resolved — dangling `STORE_PATCH.md` reference removed from `useEditorDiagramAction.ts` header. |
| R6 | ADV | ⏳ Adjudicated, decision pending — confirmed Diagram is the OUTLIER: Split/Analyze compose via `composeClientSkill` (fragments, `useEditorAgentActions.ts:28`); Diagram uses `resolvePrompt` over `DIAGRAM_PRESETS`. Options: (a) keep presets (recommended — user-editable + prompt-preview, self-contained) and correct ARCHITECTURE_PROPOSAL §5/§11; (b) wire Diagram onto fragments (needs a `'diagram'` kind in `skillCompose.ts` + a `development/diagram` skill). Behavior-changing — left for owner's call. |
| R7 | ADV | ◻ Advisory — `MermaidView.tsx` folder-convention nit. |
