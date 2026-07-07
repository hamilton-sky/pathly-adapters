# i18n + RTL — Studio UI Localization

**Feature:** `i18n-rtl`
**Scope:** Studio presentation layer only (Electron/React renderer)
**Status:** SPEC / not started · industry research folded in 2026-07-07
**Author:** design session (2026-07-07)

---

## 1. One-line thesis

**The language toggle changes only what the human reads — never what the agents receive or write.**
Studio's UI chrome becomes translatable and direction-aware (Hebrew RTL first, other
languages after). Everything "behind the glass" stays English, permanently.

---

## 2. Scope & the hard boundary

### In scope — the *presentation layer*
- Static UI chrome strings: buttons, tab/panel names, menu items, settings labels,
  empty states, toasts, tooltips, modal titles, form labels, validation copy.
- Layout **direction**: full RTL mirroring of the chrome when the UI language is RTL
  (Hebrew, later Arabic), with correctly-preserved LTR "islands" for technical content.
- A **language switcher** + persisted preference, extensible to N languages.

### Out of scope — stays English, by design (the "English brain")
Everything that is *not* human-facing chrome. The language setting must have **zero effect** on:
- Agent prompts, `core/skills/fragments/`, skills, role contracts, adapter templates.
- Board content: `comms_messages`, `comms_artifacts`, tasks, goals — the text agents post.
- FSM events (`EVENTS.jsonl`), `STATE.json`, telemetry, the SQLite DB.
- The Python orchestrator (`src/pathly_orchestrator/`), CLI engine I/O, headless argv.
- Model ids, file paths, YAML/JSON, git refs, code, terminal output.

> **Boundary test (feature-level acceptance):** with the UI set to Hebrew, capture a
> headless run's prompt and the board rows it writes — both MUST be byte-for-byte identical
> to the same run under an English UI. If the toggle can change an agent-bound byte, the
> boundary is broken.

### Separate, optional (Phase 5, off by default)
On-demand translation of *displayed* AI content (English → the view language) as a
read-only convenience — see §8. This never mutates stored content; it only renders a
translated copy on request.

---

## 3. Measured reality (why this is tractable)

Grounding from the current `studio/src/renderer` tree:

| Signal | Value | Implication |
|---|---|---|
| i18n library present today | **none** (no `i18next`/`react-intl`/`lingui`; no `getLocale` usage) | Greenfield adoption — no migration debt |
| Renderer components | ~343 `.tsx` | String extraction is the tedious axis (mechanical, incremental) |
| CSS Modules | ~262 `.module.css` | Clean styling seams; per-component migration |
| Physical-direction CSS decls | **473 across 153 files** (`margin-left`, `padding-right`, `text-align:left`, `left:`/`right:`, `border-left/right`) | The RTL axis; ~80% codemod-able |
| Logical-property CSS decls | **0** | Nothing done yet — but nothing to undo either |
| Theming | `tokens.css` `:root` custom properties | Font stack + direction tokens live in one place |
| Timestamps | shared `Intl`-based util (`utils/timestamp.ts`) | Dates/times already locale-aware — near-free |
| Native app menu | **suppressed** — `Menu.setApplicationMenu(null)` (`main/index.ts:151`) | The worst Electron RTL gap is already moot (see §4.4) |
| Local inference already bundled | `@xenova/transformers`, `node-llama-cpp` | Phase 5 needs no new cloud dependency |

**Two independent work axes:** (A) *strings* — extract hardcoded English → catalog;
(B) *direction* — physical CSS → logical + LTR islands. They can proceed in parallel.

---

## 4. Architecture

### 4.1 String layer — `react-i18next` (+ `i18next-icu`)

**Choice:** `react-i18next` (+ `i18next`), with the **`i18next-icu`** plugin enabled from
day one. Rationale (see §10.1): de-facto React standard, largest ecosystem, documented
Electron main↔renderer switch pattern, mature namespace lazy-loading, first-class typed
keys. i18next's *default* plural syntax is weaker than ICU, and Hebrew's plural rules
benefit from ICU MessageFormat — so add `i18next-icu` up front rather than retrofitting.

- **Init** in `src/renderer/src/main.tsx` (import `./i18n` before `ReactDOM.createRoot`).
- **Catalogs** under `src/renderer/src/i18n/locales/<lang>/<namespace>.json`, **bundled via
  Vite `import`** (not served from `public/`) — this dodges the documented electron-vite →
  electron-builder "works in dev, raw keys when packaged" asset bug (§4.4 / §10.3).
- `en` is the **source of truth**; `he` (etc.) derive from it.
- **Fallback = `en`** (`fallbackLng: 'en'`). A missing key renders the English string, never
  a crash or a raw key.
- **Namespaces by feature area** (mirror the component tree): `common`, `topbar`,
  `settings`, `commandCenter`, `flowEditor`, `markdownEditor`, `terminal`, `hq`, `dbExplorer`, …
- **Key convention:** semantic `namespace:area.element` (e.g.
  `settings:appearance.colorPaletteTitle`) — **never the English string as the key**; keys
  must read meaningfully to a non-programmer translator (§10.5).
- **Typed keys:** augment `i18next.d.ts` with `CustomTypeOptions`; generate types from JSON
  with `i18next-resources-for-ts` so a bad key is a compile error.
- **Rules:** no string concatenation (use interpolation `{{count}}` + ICU plurals); no
  English literal in JSX for chrome; technical tokens (model ids, paths) are **values passed
  in**, not translated substrings.

### 4.2 Direction layer — CSS logical properties + LTR islands

**Primary technique: CSS logical properties** (not a build-time flip plugin). ~96% browser
support; one ruleset serves both directions; fits the strict CSS-Modules + tokens
conventions and stays maintainable (§10.2).

Codemod the 473 physical decls with **`postcss-use-logical` as a one-time migration pass**
(not a permanent build step):

| Physical | Logical |
|---|---|
| `margin-left` / `margin-right` | `margin-inline-start` / `margin-inline-end` |
| `padding-left` / `padding-right` | `padding-inline-start` / `padding-inline-end` |
| `border-left` / `border-right` | `border-inline-start` / `border-inline-end` |
| `text-align: left` / `right` | `text-align: start` / `end` |
| `left:` / `right:` (positioning) | `inset-inline-start` / `inset-inline-end` |

Then set `dir="rtl"` on the document element (authoritatively — via the `document.dir`
effect in §4.3, not a CSS-only `direction` property, so `:dir()` and bidi isolation both
resolve correctly). Style direction-specific rules with the **`:dir(rtl)`** pseudo-class
(matches *computed* direction anywhere in the tree), not `[dir=rtl]`.

- **Codemod handles the bulk mechanically.** `left:`/`right:` in **absolute positioning**
  (popovers, drop-ups, badges, tooltips) need a **hand-audit** — some encode a genuinely
  physical "pin to this edge" intent and must NOT flip. Grep every `position: absolute|fixed`
  rule first to scope this.
- **No logical equivalent for `box-shadow` / `transform: translateX|scaleX`** — flip these
  with a signed custom property: `--x-dir: 1` default, `-1` under `:dir(rtl)`, multiplied
  into the `calc()` offset. (Your cards/popovers use both.)
- **`float`** stays physical (leave as-is or migrate to flex/grid) — `float: inline-*` has
  weaker support.
- **Icon mirroring:** directional glyphs (chevrons, arrows, back/forward, tree disclosure)
  flip via `transform: scaleX(-1)` under `:dir(rtl)`; non-directional icons (search,
  checkmark) do not.
- **Font:** append a Hebrew-capable fallback to `--font-family-base` in `tokens.css`
  (recommend **Assistant** / **Heebo** / **Rubik**, or Noto Sans Hebrew). Geist lacks
  full Hebrew coverage.

**LTR islands (the developer-tool nuance — the highest-risk item).** Much of Studio's
content is inherently LTR and must stay LTR *inside* an RTL shell:

- **Inline technical tokens** (model ids `claude-opus-4-8`, file paths, git branches, URLs,
  IDs, numbers): wrap in **`<bdi>`** — it isolates from the surrounding bidi run and fixes
  the classic number/ID "spillover" reordering bug.
- **Code / log / terminal blocks** where direction should self-determine from content: use
  **`unicode-bidi: plaintext`** (derives base direction from the first strong character)
  rather than a blanket `dir="ltr"`.
- **Whole LTR subtrees** — wrap with `dir="ltr"` (which implies `unicode-bidi: isolate`):
  - **Terminal** (xterm) — `components/Terminal/*`
  - **Code / config editors** (CodeMirror) — `MarkdownEditor/*`, `Editor/*`
  - **Diffs** — `Editor/DraftDiffViewer/*` (Split/Unified/CodeDiffView)
  - **Flow canvas** (reactflow) — `FlowEditor/VisualView/*`
  - **Diagrams** (mermaid / plantuml) — `MarkdownEditor/DiagramGalleryPanel/*`
  - **SQL / raw data** — `DBExplorer/SqlTab/*`, event/trace rows
  - **Rendered markdown code blocks** — `shared/MarkdownRenderer/*`

### 4.3 State & config

- **`languageStore`** slice (Zustand, matching the existing theme-preference pattern in
  `useStore()`): `{ lang, dir, setLang }`. `dir` is derived (`he`/`ar` → `rtl`, else `ltr`).
  No i18n library manages `dir` for you — this is an app-level concern in all of them (§10.1).
- **Persist** to `localStorage` (same mechanism as `spawnCaps` / theme).
- **Root effect** (`useDocumentDirection` hook) sets `document.documentElement.lang` + `.dir`
  from the store. Baseline stays `<html lang="en">` in `index.html`; the store overrides at
  runtime.
- **Renderer strings switch live** (react-i18next `changeLanguage()` re-renders subscribed
  components — no reload). Only *native* Chromium locale (OS dialog default-button text) is
  relaunch-gated — and Studio has effectively none of that (§4.4).
- **Switcher UI** in `Settings/AppearanceSettings` — a new "Language" section beside
  "Color Palette", using the existing `LanguageName` + `languageLabels` enum pattern
  (mirror `theme.ts` / `paletteLabels`).

### 4.4 Electron-native surface (largely a non-issue for Studio)

Scout research (§10.3) flags Electron's native chrome as the hard part of desktop i18n —
native menus have **no** i18n and **no** RTL mirroring (issue open since 2018). **Studio
already sidesteps this:**

- **Native application menu is suppressed** — `Menu.setApplicationMenu(null)`
  (`main/index.ts:151`). The topbar is custom renderer content → it localizes and mirrors
  through the same react-i18next + `dir` pipeline as everything else. No native-menu work.
- **Only native surfaces are OS file dialogs** (`dialog.showOpenDialog` /
  `showSaveDialog`, `main/index.ts`). The OS localizes and RTL-mirrors these automatically;
  no custom button labels are passed → nothing to do.
- **First-run locale detection:** use `app.getPreferredSystemLanguages()` (Electron's own
  recommendation) for the initial default, but the user's **persisted explicit choice always
  overrides**. Avoid `app.getLocale()` as ground truth (documented macOS bug).
- **Packaging:** set electron-builder **`electronLanguages`** to trim unused Chromium
  `.pak` files, and **verify translation catalogs survive the electron-vite → electron-builder
  boundary** (bundling via `import` per §4.1 avoids the `public/`-vs-`asar` "raw keys when
  packaged" failure mode).

---

## 5. Phased delivery

Each phase is independently shippable and leaves the app fully working in English.

### Phase 0 — Foundation & harness *(small)*
- Add `react-i18next` + `i18next` + `i18next-icu`; create `src/renderer/src/i18n/` (config,
  `en/common.json`, typed-keys setup).
- Add `languageStore` slice + `useDocumentDirection` hook + persistence.
- Add the Language switcher in `AppearanceSettings` (English + a stub `he`).
- Add a Hebrew font fallback to `tokens.css`.
- **Accept:** switching language flips `<html dir>`/`lang`; English unchanged; typecheck green (both tsconfigs).

### Phase 1 — RTL CSS migration *(medium — the bulk)*
- `postcss-use-logical` one-time pass: 473 physical decls → logical across 153 files.
- Hand-audit every `position:absolute|fixed` `left:`/`right:` case.
- Wrap §4.2 LTR islands (`<bdi>` inline, `unicode-bidi: plaintext` for code, `dir="ltr"` subtrees).
- Add `--x-dir` for box-shadow/transform + the directional-icon flip rule.
- **Accept:** with `:dir(rtl)` forced, chrome mirrors correctly; terminal/code/diff/canvas/paths stay LTR & correct; verified at ≤200px panel width (responsive rule); no horizontal-scroll escape.

### Phase 2 — String extraction *(tedious, mechanical, incremental)*
- Pull hardcoded English chrome strings → `en/<namespace>.json`; replace with `t()`.
- Go panel-by-panel: TopBar → Settings → CommandCenter → HQ → FlowEditor → MarkdownEditor → DBExplorer → rest. (`AppearanceSettings` — `"Color Palette"`, `"Select your preferred…"` — is a canonical first target.)
- Wire **two CI gates**: an `eslint-plugin-i18next` rule flagging bare JSX chrome literals + undefined keys, and a **key-diff script** failing the build if a locale is missing a key present in `en`.
- **Accept:** each migrated panel renders identically in `en`; CI blocks new hardcoded chrome literals and missing keys.

### Phase 3 — Hebrew catalog + GA *(small once catalog exists)*
- MT-fill `en` → `he` to get a working locale fast, then **100% human review** (even
  publication-ready MT is universally reviewed in practice; RTL context errors are easy to
  miss — §10.5).
- Ship Hebrew as a selectable language.
- **Accept:** full Hebrew chrome, mirrored, no clipping/overflow; date/number localization via the existing `Intl` util; the **§2 boundary test passes** (headless prompt + board rows identical to English).

### Phase 4 — Additional languages *(extensibility proof)*
- Add ≥1 LTR language (e.g. `es`/`ru`/`fr`) and optionally Arabic (RTL, reuses Phase 1).
- **Accept:** adding a language is *catalog-only* — no component or CSS changes.

### Phase 5 — (optional) On-demand AI-content translation *(isolated, off by default)*
See §8. Ships independently; does not gate Phases 0–4.

---

## 6. Feature-level acceptance criteria

1. Toggle to Hebrew → entire chrome in Hebrew, correctly mirrored; LTR islands intact.
2. Toggle back to English → **behavior identical to today** (no regression).
3. **Boundary:** agent prompts and board content verified English regardless of UI language.
4. Responsive: every localized panel passes the ≤200px check; no overflow escape.
5. Conventions honored: no inline styles, CSS Modules only, components within size limits,
   `type="button"`, ARIA intact; both tsconfigs typecheck clean.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Over-flipping technical content (mangled paths/code, reversed terminal) | Explicit LTR-island list (§4.2) with `<bdi>` / `unicode-bidi: plaintext`; #1 test focus |
| `left:`/`right:` codemod false positives | Absolute-position cases hand-audited, not auto-converted |
| String-extraction drift (new hardcoded literals) | `eslint-plugin-i18next` CI gate |
| Missing keys shipping as raw text | `fallbackLng: 'en'` + key-diff CI gate |
| Translation catalogs break in packaged build (electron-vite `public/`→asar) | Bundle catalogs via `import`; set `electronLanguages`; test the **packaged** build |
| Hebrew glyph gaps in Geist/Inter | Hebrew font fallback in `tokens.css` + visual QA |
| Scope creep into the backend | §2 non-goals + the boundary test as a hard gate |
| Native-menu RTL gap | **Not applicable** — native menu already suppressed (§4.4) |

---

## 8. Phase 5 detail — displayed-content translation (optional)

Agents keep writing English. This layer only renders a translated **copy** of already-stored
English content on user request, then caches it.

- **Where:** a "translate" affordance on board cards / artifact bodies / summaries.
- **Cache:** keyed by `(source-hash, target-lang)`; never re-translate unchanged text.
- **Never translate:** code, identifiers, paths, IDs, YAML/JSON — pass through + keep LTR.

**The decisive fact (§10.4):** dedicated NMT engines (NLLB, Google, DeepL) have **no
instructable "don't translate this" mechanism** — they translate everything in the span,
including `claude-opus-4-8` and file paths, unless the caller pre-masks technical tokens.
Only an **LLM** can be told inline to leave code/identifiers untouched. Since Studio's content
is English prose *mixed with* code/paths, this drives the design:

- **Default: on-device `Xenova/nllb-200-distilled-600M`** via the already-bundled
  Transformers.js (~242MB one-time download, `heb_Hebr`, offline, free, private) **+ a
  regex/AST masking pre/post-processor** that extracts technical tokens before translation
  and re-inserts them after. Best fit for local-first.
- **Opt-in "smart mode": an LLM call** (Claude, reusing the existing engine path) with a
  preserve-identifiers prompt — higher fidelity for mixed code+prose, no masking needed;
  trade-off is cloud round-trip + latency + cost.
- **Cloud NMT (Google $20/M · DeepL $25/M)** — viable fallback, same masking requirement,
  plus the privacy cost of shipping content off-box (against local-first). Not the default.
- **Eliminated:** Bergamot/Firefox Translations (no Hebrew).
- **Before committing:** run a small bake-off (NLLB-600M vs. LLM) on ~15 real English→Hebrew
  UI strings from actual content — the distilled 600M model's Hebrew quality should be
  spot-checked empirically.

---

## 9. Open decisions

| # | Decision | Status |
|---|---|---|
| 1 | Languages beyond Hebrew? (affects font stack + plural rules; Arabic reuses RTL work) | **Open** — need product input |
| 2 | Translation ops: TMS vs JSON-in-repo | **Resolved by research (§10.5):** JSON-in-repo + CI gates now; defer a TMS (Weblate self-hosted / Crowdin free-OSS tier) to 3+ languages or non-technical translators |
| 3 | Phase 5 engine default | **Recommended:** local NLLB-200 + masking, LLM opt-in — confirm after the bake-off |
| 4 | Switcher placement: Settings only, or also a topbar quick-toggle? | **Open** — minor |

---

## 10. Industry research — synthesized survey

*Compiled 2026-07-07 from 5 parallel web-research scouts. Confidence noted per area; strongest
citations inline (full source lists live in the run transcripts).*

### Recommended stack (the decision)

| Layer | Choice | Why |
|---|---|---|
| i18n library | **react-i18next** + **i18next-icu** | Largest ecosystem, documented Electron switch pattern, mature lazy-load + typed keys; ICU for Hebrew plurals |
| Direction | **CSS logical properties** (one-time `postcss-use-logical` codemod) + authoritative `dir` | ~96% support, one ruleset both ways, no permanent build step |
| Native chrome | **Custom renderer topbar** (Studio already suppresses the native menu) | Electron native menus have no i18n and no RTL mirroring |
| Translation ops | **JSON-in-repo + CI gates**; defer TMS | Right-sized for hundreds of strings / Hebrew-first / small team |
| On-demand MT (Ph. 5) | **Local NLLB-200-distilled-600M** + masking, **LLM "smart mode"** opt-in | Local-first; only an LLM can be told to leave code/paths alone |

### 10.1 i18n library — react-i18next *(confidence: med-high)*
- Largest ecosystem (~12.6M weekly downloads), "Healthy" maintenance; react-intl and LinguiJS
  are viable but smaller. LinguiJS has the best string-extraction DX + smallest bundle;
  react-intl has native ICU. i18next wins on ecosystem breadth + documented **Electron
  main↔renderer IPC switch pattern** (the exact mechanism Studio needs).
- **No library manages `dir`** — universally an app-level concern (`document.documentElement.dir`
  in a locale effect). RTL is a wash between the three.
- i18next's default plural syntax is weaker than ICU → **enable `i18next-icu` from day one**.
- Runtime switch via `changeLanguage()` + `languageChanged` event (known rough edge: ensure
  correct Suspense/hook usage so `Trans`/`t()` re-render). Typed keys via `CustomTypeOptions`
  + `i18next-resources-for-ts`.
- Sources: [react-i18next GitHub](https://github.com/i18next/react-i18next) · [Phrase — Electron i18n](https://phrase.com/blog/posts/building-an-electron-app-with-internationalization-i18n/) · [Lingui vs i18next](https://lingui.dev/misc/i18next) · [i18next TypeScript](https://www.i18next.com/overview/typescript) · [i18next-icu](https://github.com/i18next/i18next-icu)

### 10.2 RTL implementation — logical properties *(confidence: high)*
- Logical properties are the modern default for a *maintained* codebase; build-time flippers
  (`rtlcss`/`postcss-rtlcss`) are for legacy/framework cases that must keep physical CSS.
  ~96% browser support (all evergreen since ~2021).
- Migrate with **`postcss-use-logical` as a one-off script**, not a permanent build step.
  Safe to automate: `margin-*`, `padding-*`, `border-*`, `text-align:left/right`. Hand-audit:
  `left`/`right` on `position:absolute|fixed` (physical-edge vs logical-start intent).
- Set `dir` on the **document** (not CSS `direction` only) — `:dir()` and the HTML spec's
  implicit `unicode-bidi: isolate` both key off the attribute. Use `:dir(rtl)` to style by
  computed direction.
- Bidi: `<bdi>` for inline LTR tokens (fixes number/ID spillover); `unicode-bidi: plaintext`
  for code/log blocks; `dir="ltr"` wrappers for LTR subtrees.
- No logical equivalent for `box-shadow`/`transform` → signed `--x-dir` custom prop via
  `:dir()`. Directional icons flip with `scaleX(-1)`; non-directional don't.
- Sources: [MDN — Logical properties](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Logical_properties_and_values) · [MDN — `:dir()`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:dir) · [MDN — `unicode-bidi`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/unicode-bidi) · [caniuse — logical props](https://caniuse.com/css-logical-props) · [postcss-use-logical](https://github.com/mayank99/postcss-use-logical) · [Tiger Oakes — RTL tricks](https://tigeroakes.com/posts/rtl-tricks/)

### 10.3 Electron specifics *(confidence: med-high)*
- Native **Menu**, context menus, and `dialog` have **no built-in i18n**; native menus have
  **no RTL direction API** ([#11912](https://github.com/electron/electron/issues/11912), open
  since 2018). The pragmatic fix is a custom HTML/CSS menu bar — **which Studio already has**
  (`Menu.setApplicationMenu(null)`), so this is moot here.
- Native `dialog.showMessageBox` auto-translates **default** buttons via the OS; passing your
  own labels changes layout — Studio only uses file dialogs, which the OS handles.
- Locale detection: prefer `app.getPreferredSystemLanguages()`; `app.getLocale()` has a
  documented macOS bug ([#26612](https://github.com/electron/electron/issues/26612)). User
  choice overrides auto-detect.
- True Chromium-locale change (`--lang`) requires a **relaunch**; renderer React content
  switches **live** via IPC-pushed catalogs. Design UX around "renderer live; native chrome
  relaunch" — but Studio has ~no native chrome to relaunch for.
- Packaging: electron-builder bundles **all** `.pak` locales by default → trim with
  **`electronLanguages`**; and translation JSON in `public/` can 404 to raw keys when packaged
  ([#8228](https://github.com/electron-userland/electron-builder/issues/8228)) → bundle via
  `import` instead.
- Sources: [Electron `app` docs](https://www.electronjs.org/docs/latest/api/app) · [electron/electron#11912](https://github.com/electron/electron/issues/11912) · [electron-builder `electronLanguages`](https://www.electron.build/configuration.html) · [electron-vite assets](https://electron-vite.org/guide/assets.html)

### 10.4 On-demand MT *(confidence: medium)*
- **Key fact:** dedicated NMT (NLLB / Google / DeepL) can't be instructed to skip code/paths —
  caller must pre-mask. Only an **LLM** takes an inline "don't translate this" instruction. This
  is the decisive constraint for mixed prose+code content.
- **On-device** `Xenova/nllb-200-distilled-600M` (Transformers.js, already bundled): ~242MB,
  `heb_Hebr`, offline, free, private — best local-first fit. (FLORES Hebrew↔En chrF 86/BLEU 39
  is for the larger 3.3B model; spot-check the 600M variant.)
- **Cloud:** DeepL **does** support Hebrew now (June 2025) but reduced-feature + priciest
  ($25/M); Google $20/M, mature Hebrew but documented gender-agreement weakness. Both ship
  content off-box.
- **LLM (Claude):** top WMT24 quality; best for mixed code+prose (instructable); slower/costlier.
- Bergamot/Firefox Translations: **no Hebrew** → eliminated.
- Sources: [Transformers.js](https://huggingface.co/docs/transformers.js/index) · [Xenova/nllb-200-distilled-600M](https://huggingface.co/Xenova/nllb-200-distilled-600M) · [DeepL supported languages](https://developers.deepl.com/docs/getting-started/supported-languages) · [Google Translation pricing](https://cloud.google.com/translate/pricing)

### 10.5 Localization ops *(confidence: med-high)*
- For hundreds of strings / Hebrew-first / small team: **JSON-in-repo + CI**, not a TMS.
  Adopt a TMS (Weblate self-hosted = free; Crowdin free-OSS tier) only at 3+ languages or when
  non-technical translators need a web UI.
- Keys: **semantic `namespace:feature.key`** (never English-as-key); namespaced files
  lazy-load and stay reviewable in diffs.
- CI: `eslint-plugin-i18next` (flag hardcoded literals / undefined keys) + a key-diff gate
  (fail if a locale misses a key present in `en`); `fallbackLng` as the runtime net.
- New-language bootstrap: **MT-fill then 100% human review** — even publication-ready MT is
  universally reviewed in practice; RTL context errors slip through silently.
- Sources: [Locize — i18n key naming](https://www.locize.com/blog/guide-to-i18n-key-naming/) · [Lokalise — key conventions](https://lokalise.com/blog/translation-keys-naming-and-organizing/) · [Weblate continuous localization](https://docs.weblate.org/en/latest/admin/continuous.html) · [Crowdin 2026 AI translation survey](https://crowdin.com/blog/ai-translation-enterprise-survey-2026)

### Overall confidence
**Med-high.** Library choice, RTL technique, Electron behavior, key-naming, and CI tooling are
each corroborated across ≥2 independent authoritative sources. Softer spots: exact TMS pricing
(changes fast — verify live), Hebrew-specific MT quality benchmarks (DeepL Hebrew too new for
independent head-to-heads; the NLLB score cited is for the larger model) — hence the §8 bake-off
before finalizing the Phase 5 engine.
