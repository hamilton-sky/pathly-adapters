---
name: pathly-design
description: Use this skill to generate well-branded interfaces and assets for Pathly (Pathly Studio + the pathly-adapters CLI), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping a dark-first, developer-grade FSM agent-pipeline cockpit.
user-invocable: true
---

Read the `readme.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out
and create static HTML files for the user to view. If working on production code, you can
copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build
or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_
production code, depending on the need.

## Quick orientation
- **Brand:** Pathly — a local desktop cockpit for driving/observing AI agent FSM pipelines.
  Dark-first, dense, developer-grade. Sky-blue accent (`#38BDF8`, "bright sky"), monospace
  numbers, pipeline-state color as the core domain language.
- **Entry point:** link `styles.css` — it `@import`s all tokens + the Geist / Geist Mono
  `@font-face` rules. Everything keys off CSS custom properties; never hard-code hex.
- **Themes:** 12 palettes via `[data-theme="…"]` on a wrapper; default `:root` is Pathly Dark.
- **Icons:** lucide. A self-hosted subset is in `assets/vendor/icons.js`
  (`PathlyIcons.svg('menu',{size:14})`). The brand mark is `assets/logo-mark.svg`.
- **Components:** `components/<group>/<Name>.jsx` (+ `.d.ts`, `.prompt.md`). Read each
  `.prompt.md` for usage. Button, IconButton, Input, Select, Badge, StatePill, ProgressBar,
  Spinner, Tabs, Card, Tooltip, ContextMenu.
- **UI kits:** `ui_kits/{db-explorer,monitor,flow-canvas,skill-notebook}/` are full-screen,
  interactive, pixel-faithful recreations. `ui_kits/_shell/` is the shared topbar + sidebar.
- **Slides:** `slides/` — 1280×720 branded templates.

## Working rules
- Title Case buttons, UPPERCASE+spaced section labels, sentence-case body, lowercase mono
  for commands/paths/IDs. Numbers always in Geist Mono. No emoji.
- Borders (not shadows) at rest; shadows only for floating surfaces. Radii small (5px).
  4px spacing base. Fast `100–150ms ease-out` motion, gated on reduced-motion.
- Sky-blue = interactive/active/focus. Orange = running/reroute pipeline state.
- For self-contained HTML artifacts, render with self-hosted React UMD + `icons.js`
  (`assets/vendor/`) and `React.createElement`, or write plain HTML/CSS + vanilla JS like
  the UI kits do — no external CDN is required.
