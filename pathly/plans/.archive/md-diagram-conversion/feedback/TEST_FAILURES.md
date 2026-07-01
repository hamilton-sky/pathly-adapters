# TEST_FAILURES.md — md-diagram-conversion (Phase 8 Acceptance Test)

**Tester:** Claude Code (supervised) · **Date:** 2026-06-30
**Method:** static verification (typecheck, code/text checks) + live observation from the owner
dogfooding the feature in a running Studio (Mermaid render, gallery, lightbox, and Arrange mode
were exercised on-screen). Stories that need a specific interaction not yet observed are marked
**MANUAL-REQUIRED** with exact steps.

## Result: no failures found
No story FAILED. S-12 passes statically; several stories were verified live; the remainder are
MANUAL-REQUIRED (listed below) — none are blocked or broken.

---

## Per-story

| Story | Status | Notes |
|---|---|---|
| S-01 Diagram pill in header | ✅ Verified live | Third pill present and used to generate diagrams. |
| S-02 Run generates source | ✅ Verified live | Runs spawn, sidecar written, cards appear. **Run-guard** (double-click no-op) = MANUAL: click Run twice fast, confirm one spawn. |
| S-03 Sidecar persists on reload | ⚠ MANUAL-REQUIRED | Generate a diagram → close the file → reopen → cards should reload from `<file>.diagrams.json`. |
| S-04 Gallery panel + cards | ✅ Verified live | Cards render with badge/status/date/engine; panel is the right-docked shape. |
| S-05 Mermaid renders as SVG | ✅ Verified live | Confirmed on-screen (lightbox screenshots). |
| S-06 ASCII in `<pre>` | ⚠ MANUAL-REQUIRED | Generate an ASCII diagram → card + lightbox show a monospace `<pre>`. |
| S-07 PlantUML source + notice | ◑ Static pass + MANUAL | Notice text now matches S-07 exactly (grep-confirmed). MANUAL: generate a PlantUML diagram → see source `<pre>` + the notice; confirm no network request. |
| S-08 Lightbox zoom/pan + Esc/backdrop | ✅ Verified live | Lightbox opened with zoom/pan (screenshots). **Esc/backdrop close** = MANUAL: press Esc, click backdrop. |
| S-09 Delete card + last-delete closes panel | ⚠ MANUAL-REQUIRED | Delete a card (gone on disk after reload); delete the last card → panel closes. |
| S-10 Regenerate appends | ⚠ MANUAL-REQUIRED | Click Regenerate → a NEW card is appended (old one not overwritten). |
| S-11 Panel auto-opens on completion | ◑ Verified live + MANUAL | Panel opened after a run. MANUAL: start a run, switch to another file before it finishes → panel must NOT open for the current file. |
| S-12 Typecheck clean | ✅ PASS | `npm run typecheck` and `tsc -p tsconfig.node.json` both exit 0 (re-run this session). |
| S-13 Theme re-render | ⚠ MANUAL-REQUIRED | Open a Mermaid diagram → flip Studio light/dark → SVG re-renders with new tokens. Hex-fallback rule (reconciled) = static pass. |

## Beyond the original stories (verified live this session)
- **Lightbox UX:** soft dot-grid, fit-to-viewport, zoom 0.5×–8×, action toolbar (copy/SVG export).
- **Arrange mode:** flowchart Mermaid → draggable React Flow canvas with dagre layout, multi-line
  node labels, header Back button, Save layout → sidecar. Verified on-screen.

## Manual smoke checklist (to fully clear S-03/06/07/09/10/13)
1. Generate one Mermaid, one ASCII, one PlantUML on a `.md` file.
2. Reload the file → all three cards return (S-03).
3. ASCII shows `<pre>`; PlantUML shows source + the exact notice (S-06/S-07).
4. Delete one → gone after reload; delete all → panel closes (S-09).
5. Regenerate one → new card appended (S-10).
6. Flip theme → Mermaid SVG re-renders (S-13).
