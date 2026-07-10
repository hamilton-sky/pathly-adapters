# i18n + RTL — Implementation Plan

**Feature:** `i18n-rtl` · **Scope:** Studio presentation layer only (Electron/React renderer)
**Board goal:** `88232538-771d-4b97-90d8-e0a78518bbb6` (executor `loop`)
**Companion:** [SPEC.md](SPEC.md) — design + industry research + §11 review addendum
**Drafted:** 2026-07-09 · folds in the 2026-07-09 codebase-review gaps (SPEC §11)

---

## How to read this

This is the **build work-list** — the board DAG made legible. Phases 0–5 already exist as
board tasks (seeded 2026-07-07 under the goal above); this plan is authoritative over their
text where the two differ, because it folds in the six review gaps the original tasks predate.

Each phase maps to **one existing board task** (ID given). The review gaps are added as **five
new sibling tasks** (`T-A`…`T-E`) rather than by rewriting the originals — additive and
reversible, mirroring how SPEC §11 was layered on top of the original spec. The `loop` executor
drains every *ready* task on the frontier, so a sibling task is picked up exactly like a phase.

> **One stale line to fix.** The existing **Phase 3** task still says dates are "localized via
> the existing Intl timestamp util." The review found that util can't do it as-is (module-scope
> formatters, `locale=undefined`). `T-C` supersedes that clause — see §4.

---

## 1. The DAG at a glance

| # | Task | Board task ID | Depends on | Status |
|---|---|---|---|---|
| 0 | Foundation & harness | `ea95b1b0` | — | pending (ready) |
| 1 | RTL CSS migration | `e19e1061` | 0 | pending |
| 2 | String extraction | `706a31bf` | 0 | pending |
| 3 | Hebrew catalog + GA | `80c0441e` | 1, 2 | pending |
| 4 | Additional languages | `49053723` | 3 | pending |
| 5 | On-demand AI translation *(optional)* | `9593e07c` | 0 | pending |
| **T-A** | **Direction beyond CSS** *(→ augments 1)* | *new* | 0 | to post |
| **T-B** | **Attribute-string i18n + lint** *(→ augments 2)* | *new* | 0 | to post |
| **T-C** | **Bind date/number formatter to language** *(→ augments 3)* | *new* | 0 | to post |
| **T-D** | **Boundary-diff CI gate + cliEngine lint bar** *(guardrail)* | *new* | 0 | to post |
| **T-E** | **RTL screenshot-diff smoke gate** *(QA)* | *new* | 1, T-A | to post |

Two parallel axes come off Phase 0: **direction** (1 + T-A + T-E) and **strings** (2 + T-B).
Both must land before **Phase 3** (Hebrew GA), which is gated by the boundary test (T-D) and the
date binding (T-C). Phase 5 is independent and off by default.

---

## 2. The invariant every task serves

**The language toggle changes only what the human reads — never an agent-bound byte.** The
renderer is *not* purely presentational (it composes prompts in `services/cliEngine.ts`), so the
discipline is: `t()` wraps chrome strings and **never** a prompt-composition string.

- **Boundary test (hard gate, `T-D`):** a Hebrew-UI headless run's prompt + the board rows it
  writes are **byte-for-byte identical** to the same run under English.
- **CI gates by GA:** (1) `eslint-plugin-i18next` — bare chrome literals **incl. attributes**;
  (2) key-diff — a locale missing an `en` key fails the build; (3) boundary diff (`T-D`);
  (4) RTL screenshot smoke (`T-E`).

---

## 3. Phases

### Phase 0 — Foundation & harness · `ea95b1b0` · deps: —
**Objective.** Stand up the i18n machinery with zero visible change in English.
**Work.** `react-i18next` + `i18next` + `i18next-icu`; `src/renderer/src/i18n/` (config,
`en/common.json`, typed keys via `CustomTypeOptions` + `i18next-resources-for-ts`); a
`languageStore` Zustand slice + `useDocumentDirection` hook (sets `documentElement.lang`/`.dir`)
+ `localStorage` persistence; a Language section in `Settings/AppearanceSettings` (English +
stub `he`); a Hebrew font fallback (Assistant/Heebo/Rubik) in `tokens.css`; init i18n in
`main.tsx` before render.
**Files.** `studio/src/renderer/src/i18n/*`, `main.tsx`, `store/`, `AppearanceSettings`,
`styles/tokens.css`, `index.html`.
**Accept.** Switching flips `<html dir>`/`lang`; English UI byte-identical to today; both
tsconfigs typecheck clean.

### Phase 1 — RTL CSS migration · `e19e1061` · deps: 0
**Objective.** Mirror the chrome under RTL while technical content stays LTR.
**Work.** `postcss-use-logical` one-time pass: **477 physical decls → logical across 154
`.module.css` files** (reconfirmed 2026-07-09); hand-audit every `position:absolute|fixed`
`left:`/`right:`; wrap LTR islands (Terminal/xterm, CodeMirror, DraftDiffViewer, reactflow,
mermaid, SqlTab, markdown code blocks) with `dir="ltr"` / `unicode-bidi:plaintext`, and `<bdi>`
for inline tokens; add a signed `--x-dir` custom prop via `:dir(rtl)` for box-shadow/transform;
flip directional icons with `scaleX(-1)`.
**Files.** `studio/src/renderer/**/*.module.css`, `tokens.css`, the LTR-island components.
**Accept.** With `:dir(rtl)` forced, chrome mirrors; terminal/code/diff/canvas/paths stay LTR;
verified at ≤200px panel width; no horizontal-scroll escape.
**Review add → see `T-A`:** direction logic outside CSS (TSX inline styles, JS positioning,
arrow keys) is NOT covered by the codemod.

### Phase 2 — String extraction · `706a31bf` · deps: 0
**Objective.** Every chrome string comes from a catalog, not a literal.
**Work.** Pull hardcoded English chrome → `i18n/locales/en/<namespace>.json`, replace with
`t()`; panel-by-panel (TopBar → Settings → CommandCenter → HQ → FlowEditor → MarkdownEditor →
DBExplorer → rest); wire the two lint/key-diff CI gates; `fallbackLng:'en'`; semantic
`namespace:feature.key` keys.
**Files.** `studio/src/renderer/**/*.tsx`, `i18n/locales/en/*`, CI config.
**Accept.** Each migrated panel renders identically in `en`; CI blocks new hardcoded literals +
missing keys.
**Review add → see `T-B`:** ~424 human-facing strings live in **attributes** (aria-label/
title/placeholder) — not JSX text; the lint gate must cover them.

### Phase 3 — Hebrew catalog + GA · `80c0441e` · deps: 1, 2
**Objective.** Ship Hebrew as a first-class, mirrored language.
**Work.** MT-fill `en → he`, then **100% human review**; ship Hebrew as selectable.
**Files.** `i18n/locales/he/*`.
**Accept.** Full mirrored Hebrew chrome, no clipping/overflow; dates/numbers localized (**via
`T-C`, not the util as-is**); the **boundary test passes** (`T-D`).
**Review correction → see `T-C`:** the original "localized via the existing Intl util" clause is
wrong; the util needs store-binding first.

### Phase 4 — Additional languages · `49053723` · deps: 3
**Objective.** Prove extensibility is catalog-only.
**Work.** Add ≥1 LTR language (es/ru/fr) and optionally Arabic (reuses Phase 1 RTL work).
**Accept.** Adding a language requires **no component or CSS changes** — catalog only.

### Phase 5 — On-demand AI-content translation *(optional, off by default)* · `9593e07c` · deps: 0
**Objective.** Render a translated **copy** of stored English content on request; never mutate it.
**Work.** A "translate" affordance on board cards/artifacts/summaries, cached by
`(source-hash, target-lang)`. Default engine: on-device `Xenova/nllb-200-distilled-600M`
(Transformers.js, already bundled) + a regex/AST masking pre/post-processor protecting
code/identifiers/paths; opt-in LLM "smart mode" (Claude via the existing engine path). Run a
~15-string NLLB-vs-LLM bake-off first. **Never translate** code/paths/ids/YAML.
**Accept.** Selecting a card renders a Hebrew copy; code/paths preserved; stored content
unchanged; translations cached. Does not gate Phases 0–4.

---

## 4. Review-gap tasks (additive · SPEC §11)

Each is a real work item the original DAG didn't carry. Posted as siblings under the goal, with
`context_refs` → this plan.

- **`T-A` · Direction beyond CSS** *(augments Phase 1; deps: 0)* — the `postcss` codemod only
  rewrites `.css`. Inventory + fix the **~44 physical-direction sites in `.tsx`/`.ts`** (inline
  styles like `paddingLeft` tree-indent; **JS-computed positioning** reading
  `getBoundingClientRect()` into `{top,left}` in `Tooltip.tsx`, `CommentConfigButton.tsx`) and
  the **10 `ArrowLeft`/`ArrowRight` handlers** (`SlideCarousel`, `DiagramLightbox`,
  `EditorHeader`, `Monitor/TabBar`, `BoardEvalConfig`). JS offsets derive from the active `dir`;
  key handlers read `dir` (ArrowLeft = *next* under RTL). **Highest new RTL risk.**
- **`T-B` · Attribute-string i18n + attribute-aware lint** *(augments Phase 2; deps: 0)* —
  extract the **~424** `aria-label` (277) / `title` (101) / `placeholder` (46) strings; configure
  `eslint-plugin-i18next` to flag **attributes**, not only JSX children, so a11y/tooltip copy
  can't ship untranslated on a green build.
- **`T-C` · Bind date/number formatter to language** *(augments Phase 3; deps: 0)* —
  `utils/timestamp.ts` builds `Intl.DateTimeFormat(undefined, …)` at **module scope**: it follows
  the OS locale, not the toggle, and can't re-bind on a live switch. Refactor to a factory/hook
  keyed off `languageStore`; rebuild on `changeLanguage`. **Supersedes the stale Phase-3 clause.**
- **`T-D` · Boundary-diff CI gate + `cliEngine` lint bar** *(guardrail; deps: 0)* — promote the
  §2 boundary test to CI (Hebrew-UI headless prompt + board rows == English, byte-for-byte); add
  a lint/allowlist forbidding `t()` inside `services/cliEngine.ts` and any prompt-composition
  module.
- **`T-E` · RTL screenshot-diff smoke gate** *(QA; deps: 1, T-A)* — a Playwright/screenshot smoke
  pass over the **top ~20 panels in both directions**, catching clipping/overflow/island-bleed
  that manual "eyeball at ≤200px" misses across 344 components.

---

## 5. Sequencing (SPEC §11.6)

Phases 1 and 2 each sweep nearly every component. Run as two separate passes, each file opens
twice and eats merge churn. **Co-migrate per panel** — strings + attributes + direction +
arrow-keys land together in one PR per panel, in the Phase-2 panel order — while keeping the axes
conceptually distinct. Phase 2 is the largest cost and the most likely to stall: give it explicit
per-panel milestones, not one "mechanical" bucket.

---

## 6. Definition of done (feature-level)

1. Hebrew → entire chrome mirrored; LTR islands intact.
2. English → behavior identical to today (no regression).
3. Boundary: agent prompts + board content verified English regardless of UI language (`T-D` in CI).
4. Every localized panel passes the ≤200px check; no overflow escape (`T-E` smoke in CI).
5. Conventions honored — CSS Modules only, ARIA intact, `type="button"`, both tsconfigs clean.
