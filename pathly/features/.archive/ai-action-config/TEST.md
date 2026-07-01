# TEST — ai-action-config

## Automated (gating)
| Check | Command | Result |
|---|---|---|
| Renderer typecheck | `tsc --noEmit -p studio/tsconfig.web.json` | ✅ clean |
| Main typecheck | `tsc --noEmit -p studio/tsconfig.node.json` | ✅ clean |

## Acceptance criteria (USER_STORIES.md) — status
- **Story 1 (Evaluate unchanged):** ✅ Evaluate surface not modified (kept as reference per user decision).
- **Story 2 (Split presets):** ✅ preset dropdown present; default byte-identical; Use-once/Save-default/engine + legacy migration preserved. EXTRA INSTRUCTIONS textarea added (enhancement).
- **Story 3 (Analyze lenses):** ✅ lens dropdown present; default byte-identical; EXTRA INSTRUCTIONS added.
- **Story 4 (Comments engine):** ✅ engine selectable in card ("Send to {engine}") and panel header default; both send paths use `buildCliArgv`; `CLI_KEY_COMMENT` persists.
- **Story 5 (Comment presets):** ✅ verbs from shared `commentVerbs.ts` (also used by `SelectionTooltip`); default reproduces today's behavior; card now exposes the full ACTION + EXTRA config.
- **Cross-cutting:** ✅ all surfaces use the shared `PromptActionConfig` + `CliSelect`; Evaluate is the only skill-backed preset surface; no inline styles; component size guide respected.

## Manual UI (human-in-the-loop)
- Comment-defaults popover no longer clipped, sized like Evaluate, with extra textarea — **confirmed by user** ("looks good").
- Comment card full config — pending user's next reload (functional + typecheck verified).

No TEST_FAILURES. Proceeding to RETRO.
