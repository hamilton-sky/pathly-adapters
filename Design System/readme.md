# Pathly Design System

The design system for **Pathly Studio** — a local desktop cockpit for driving and
observing AI agent workflows. This project is the single source of truth for Pathly's
visual language: tokens, fonts, reusable components, full-screen UI-kit recreations,
and branded slide templates.

> **One-line brand:** dark-first, dense, developer-grade tooling. Sky-blue accent
> ("bright sky"), monospace numbers everywhere, calm surfaces, pipeline-state color
> as the core domain language.

---

## 1 · Product context

Pathly turns ad-hoc agent prompting into an **observable finite-state-machine (FSM)
pipeline**. A feature flows through stages — `PLANNING → BUILDING → REVIEWING →
TESTING → DONE` — each owned by a specialized agent (planner, builder, reviewer,
tester, retro). Every transition, token and dollar is logged.

Two surfaces make up the product:

| Surface | What it is |
|---|---|
| **`pathly-adapters` (CLI)** | `pathly-setup` stitches Pathly agents + skills into the AI host tools (**Claude Code, Codex, Copilot**). Terminal-first. |
| **Pathly Studio (Electron app)** | The visual cockpit. Panels: **Canvas** (visual FSM flow editing), **Skill Notebook** (cell-based skill editor), **Monitor** (live FSM events + metrics), **DB Explorer** (pipeline database dashboard), **HQ** (chat-driven control), **Terminal**, **Settings**. |

Core domain vocabulary: *pipeline, FSM, stage, conversation, agent, skill, flow, gate,
reroute, retro, telemetry, host, adapter, transition.*

### Sources this system was built from

- **Codebase:** `pathly-adapters/` (local mount). The authoritative design lives in
  `studio/src/renderer/src/` — `theme.ts`, `styles/tokens.css`, `styles/buttons.css`,
  `components/ui/*`, and the panel components under `components/{Monitor,FlowEditor,SkillNotebook,sidebar,topbar}/`.
- **Design explorations:** `pathly/pathly-design/` (HTML previews + scrap screenshots).
- **Engine docs (not bundled here):** `github.com/hamilton-sky/pathly`.
- Geist + Geist Mono webfonts were lifted from the shipped `@fontsource` packages;
  the lucide icon subset was extracted from the project's `lucide-react@1.16.0`.

> **Note on the accent.** Early exploration screenshots show an **orange** primary.
> The shipped code (`tokens.css`, `TopBar.module.css`, `Sidebar.module.css`) uses
> **sky-blue `#38BDF8`** as the canonical accent for everything interactive (active
> nav, focus, primary fill). Orange `#f97316` is reserved for the **running / reroute**
> pipeline state. This system follows the shipped code.

---

## 2 · Content fundamentals

How Pathly writes. Match this in any copy you generate.

- **Voice:** developer-to-developer. Direct, concise, technically precise. No marketing
  fluff, no exclamation points, no emoji in product UI.
- **Person:** mostly implied second person / imperative. Tooltips read like terse
  instructions — e.g. *"Open multiple projects simultaneously in separate windows."*
- **Casing:**
  - **Title Case** for buttons & actions: `Run Migration`, `Export Skill`, `Export JSON`, `Auto-layout`.
  - **UPPERCASE + letter-spacing** for section labels: `WORKSPACE`, `STATE MACHINE · 9 TRANSITIONS`, `COST PER INVOCATION`, `COMPOSED SKILL · 6 CELLS`.
  - **Sentence case** for body copy and descriptions.
  - **lowercase `mono`** for commands, identifiers, paths, skills: `pathly-setup --apply`, `/pathly build`, `fsm-server-sqlite`, `fix/build`, `pathly/plans/*/pathly.db`.
- **Numbers are data.** Tokens, costs, durations, IDs, timestamps and counts always
  render in Geist Mono: `290,749`, `$3.64`, `6m 29s`, `09:02:11`, `3/3`.
- **Status reads as state.** UI speaks in FSM terms: `DONE`, `BUILDING`, `REVIEWING`,
  `runner: finished`, `↩ REVIEWING → BUILDING`.
- **Density over decoration.** Short labels, tight rows, no hand-holding. The interface
  trusts the user is technical.

Representative strings: *"Command center above your AI model orchestrators"* (HQ),
*"FIXING stage for the quick-fix flow. Fast, focused, minimal — one targeted change."*
(a skill body), *"runner: finished · 290,749 tok · $3.64"* (a status line).

---

## 3 · Visual foundations

### Color
- **Dark-first.** Default palette is *Pathly Dark*: app `#111827`, deepest chrome
  `#0B0F1A`, cards `#1E2433`, raised `#283044`, terminal `#0d1117`.
- **Accent — "bright sky" `#38BDF8`.** Every interactive affordance: active nav (filled,
  white text), focus ring, primary button fill, selected tabs, links.
- **Signal hues:** blue `#60A5FA`, green `#34D399`, red `#f87171`, yellow `#FCD34D`,
  teal/runtime `#2DD4BF`, orange `#f97316`, purple `#a78bfa`.
- **Pipeline-state colors** are the core domain language: PLANNING = gray,
  BUILDING = blue, REVIEWING = orange, TESTING = purple, RETRO = teal, DONE = green.
- **Tints are derived** with `color-mix` — accent surfaces are 13% accent on transparent;
  borders 35–40%; hover fills stronger. Never hand-pick a tint; mix from the base.
- **12 shipped palettes** attach via `[data-theme="…"]` (Pathly Dark/Light, Nord, Mocha,
  Dracula, Rosé Pine, Solarized ±light, Catppuccin Latte, Paper, Dawn, Mint). Each
  overrides ~14 base values; every tint/semantic/state token re-resolves automatically.
- **Brand gradient** (blue→indigo→violet, `135deg #60A5FA → #818CF8 → #A78BFA`) is used
  *only* for the logo mark and rare hero flourishes — never as a UI surface or button.

### Type
- **Geist** for all UI; **Geist Mono** for numbers, code, IDs, paths, terminal.
- Dense fixed scale: `10 / 11 / 13 / 14 / 16px` (13 is base UI text). Display sizes
  `22 / 32 / 44px` are for slides & marketing only.
- Weights: 400 / 500 / 600 (700 for display). Section labels: 11px, 600, `0.06em`,
  uppercase. Display headings use tight negative tracking (`-0.02em`).

### Spacing, radii, borders
- **4px spacing base**, tight throughout (`2 4 6 8 12 16 20 24 32 40 48`).
- **Radii are small:** 3 / 4 / **5** (the workhorse, buttons & inputs) / 8 (cards) /
  12 (modals/panels) / full (pills, progress, dots).
- **Borders** are 1px hairlines (`#283044` / `#1E2433`). Cards = surface fill + hairline
  border + 8px radius (no drop shadow at rest). Hover lifts the border to accent.
- **Left-accent bars** (3px) classify things: cell type in the Notebook (accent=body,
  green=fragment), node agent in the Canvas (blue/purple/amber/green), active sidebar row.

### Elevation
- Shadows are **reserved for floating surfaces only** — dropdowns (`md`), popouts (`lg`),
  modals (`modal`, a deep `0 24px 64px rgba(0,0,0,.55)`). Resting surfaces use borders,
  not shadows.

### Motion
- Fast and functional: `100–150ms ease-out` on color/background/border. No bounce, no
  long easings on UI.
- **Purposeful animation only:** the FSM "active" node pulses (cyan ring), new event-log
  rows flash once, the live indicator blinks. All gated on
  `prefers-reduced-motion: no-preference`.

### Interaction states
- **Hover:** subtle — bordered buttons shift to a 12% accent fill + accent border + accent
  text; ghost/menu rows fill to `--bg-surface1`; icon buttons fill to surface + accent icon.
- **Active/pressed:** slightly stronger accent fill (≈22%).
- **Focus:** always a visible `2px solid accent` ring, offset 2px.
- **Disabled:** 0.5 opacity, `not-allowed`.

### Backgrounds & texture
- Mostly flat token surfaces. Two textures recur: a **dotted grid** (radial-dot,
  ~22–34px) on canvases and title slides, and a soft **radial accent glow** behind hero
  content. No photography, no illustration, no noise/grain.

### Layout rails
- Fixed topbar `44px`, sidebar `248px`, terminal drawer `240px`. Thin `5px` scrollbars.
- Content is dense and grid-driven; metrics use mono values with small uppercase labels.

---

## 4 · Iconography

- **Library:** [lucide](https://lucide.dev) — `lucide-react` in the app (2px stroke,
  round caps/joins, 13–16px in chrome). This system **self-hosts a curated lucide subset**
  at `assets/vendor/icons.js` (extracted from `lucide-react@1.16.0`, ISC) so cards and
  kits render with **no CDN dependency**. Use `PathlyIcons.svg('name', {size})` or place
  `<i data-icon="name" data-size="14"></i>` and call `PathlyIcons.inject()`.
- **Common icons:** `menu, brain, activity, layout-grid, book-open, database, hard-drive,
  square-terminal, settings, diamond, search, download, refresh-cw, play, pause, x,
  chevron-down/right, trash-2, pencil, plus, more-horizontal, undo-2, redo-2, circle-check`.
- **Brand mark:** a custom gradient rounded-square "P" (`assets/logo-mark.svg`) — the app
  & dock icon. It is the *only* hand-authored SVG; everything else is lucide.
- **Unicode glyphs** appear sparingly as domain symbols: `●` (live dot), `▶` (start state),
  `↩` (reroute), `✓` (done/pass), `›` (breadcrumb), `↑ ↓` (token in/out). **No emoji.**

---

## 5 · Index / manifest

### Root
- `styles.css` — the entry point consumers link. `@import`s only.
- `tokens/` — `fonts.css`, `colors.css` (+ 12 palettes), `typography.css`, `spacing.css`.
- `assets/` — `logo-mark.svg`, `fonts/` (Geist + Geist Mono woff2), `vendor/` (self-hosted
  React UMD + `icons.js`).
- `readme.md` (this file) · `SKILL.md` (Agent-Skill manifest).

### Components (`components/`) — `window.DesignSystem_ba588c.<Name>`
| Group | Components |
|---|---|
| `buttons/` | **Button** (primary · cta · secondary · ghost · destructive), **IconButton** |
| `forms/` | **Input**, **Select** |
| `feedback/` | **Badge**, **StatePill** (the FSM-stage pill), **ProgressBar**, **Spinner** |
| `navigation/` | **Tabs** (underline · pill) |
| `surface/` | **Card** |
| `overlay/` | **Tooltip**, **ContextMenu** |

Each directory holds `<Name>.jsx` + `<Name>.d.ts` + a `*.prompt.md`, and one
`@dsCard`-tagged HTML specimen.

### Foundation cards (`guidelines/`)
Type (scale, display, mono, labels) · Colors (accent, surfaces, text, signal, states,
12 themes) · Spacing (scale, radii, elevation) · Brand (logo, gradient).

### UI kits (`ui_kits/`) — full-screen interactive recreations
| Kit | What it shows |
|---|---|
| `db-explorer/` | Pipeline-database dashboard: stats strip, feature grid, timeline + agents-cost modal. |
| `monitor/` | Live FSM view: stepper, metrics, color-coded event log. **Click a phase** → configure its prompt, CLI host, agent & skill, or open the skill in the Notebook. |
| `flow-canvas/` | Visual FSM editor: node graph (forward + reroute edges), node inspector, YAML view. |
| `skill-notebook/` | Cell-based skill editor with live composed-skill preview. Reads `?skill=`. |
| `_shell/` | Shared topbar + sidebar chrome (`shell.css`, `shell.js`) used by every kit. |

### Slides (`slides/`)
`title` · `pipeline` · `metrics` · `quote` — 1280×720 branded specimens.

---

## Rendering note (for contributors)
Component cards & UI kits are **self-hosted** (no CDN, no Babel): they load React UMD +
`icons.js` + `_ds_bundle.js` from `assets/vendor`, and mount with `React.createElement`.
UI kits are intentionally vanilla HTML/CSS + JS for pixel fidelity and offline rendering.
`_ds_bundle.js`, `_ds_manifest.json` and `_adherence.oxlintrc.json` are **generated** —
never edit them by hand.
