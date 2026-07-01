# Research — md-diagram-conversion

_Researched: 2026-06-29. External findings only — cite, don't assert. All claims are sourced; unresolved risks are flagged._

The primary external unknown for this feature is the **mermaid v10/v11 API surface** — specifically the `render()` call signature, supported `themeVariables` keys, singleton initialization safety, Vite/Electron dynamic-import behavior, and security level semantics. Everything else in the architecture (React hooks, Zustand store patterns, Electron IPC via `window.pathly.fs`, SVG zoom/pan via CSS transforms) is familiar stack with no new dependencies requiring external research.

---

## Q1: mermaid.render() API (v10 / v11)

**Current signature:**
`render(id: string, text: string, container?: Element): Promise<{ svg: string, bindFunctions?: (el: Element) => void }>`

- The `id` string is still required in v10 and v11 — it has not been replaced by a container element. The optional third `container` argument was added in v10+ but is not mandatory. [(mermaid usage docs)](https://mermaid.js.org/config/usage.html), [(DeepWiki core API)](https://deepwiki.com/mermaid-js/mermaid/2-core-api)
- `bindFunctions` is a returned function that wires interactive events (tooltips, click handlers) onto the SVG after it is inserted into the DOM. For **display-only** renders (our use case), it can be safely omitted — no interactivity needed. [(mermaid usage docs)](https://mermaid.js.org/config/usage.html)
- `mermaid.init()` is **deprecated** in v10; `mermaid.run()` is the preferred integration for auto-processing DOM nodes. Neither is relevant here — we call `render()` directly. [(mermaid usage docs)](https://mermaid.js.org/config/usage.html)
- **v11 breaking change (CDN only):** the CDN build switched from UMD to IIFE, requiring `mermaid.default.<fn>`. ESM / npm imports are **unaffected** — `import mermaid from 'mermaid'` still works. [(v11 breaking changes discussion #4710)](https://github.com/orgs/mermaid-js/discussions/4710)
- **Concurrency:** mermaid cannot process concurrent `render()` calls — parallel calls without `await` fail. The per-file run-guard in the architecture (one in-flight diagram run per file) already prevents this. [(mermaid discussion #4091)](https://github.com/orgs/mermaid-js/discussions/4091)

---

## Q2: themeVariables

**Key constraint:** `themeVariables` only works with `theme: 'base'`. Setting them against `default`, `dark`, `forest`, or `neutral` has no effect. [(mermaid theming docs)](https://mermaid.ai/open-source/config/theming.html)

| Design intent | themeVariable key |
|---|---|
| Diagram backdrop | `background` |
| Node fill / background | `primaryColor` (→ derives `mainBkg` for flowchart rects) |
| Text inside nodes | `primaryTextColor` (alias: `nodeTextColor`) |
| Node border | `primaryBorderColor` |
| Edge / link color | `lineColor` / `defaultLinkColor` |
| Alternate node fills | `secondaryColor`, `tertiaryColor` |
| Font | `fontFamily`, `fontSize` |
| Dark mode flag | `darkMode` (bool — affects derived color math) |

- **Only hex codes are honored.** CSS named colors and `var(--token)` strings are not supported — must resolve CSS custom properties to hex via `getComputedStyle` first. [(mermaid theme customization)](https://mermaid.ai/docs/style-and-customize/create-custom-styles)
- `themeVariables` are applied at `initialize()` time and are **global** — there is no confirmed per-render override path. Changing them requires calling `initialize()` again (see Q3 risk).

---

## Q3: Singleton / module cache pattern

- ES module caching gives a natural singleton: `import('mermaid')` resolves the same module object within a process. [(Ben Nadel: module singletons)](https://www.bennadel.com/blog/4327-caution-your-javascript-node-module-might-be-a-singleton-anti-pattern.htm)
- Recommended React pattern: **module-level cached Promise** that wraps a single `mermaid.initialize()` call. Subsequent calls check the promise rather than calling initialize again. A `useLayoutEffect` with an empty dep array triggers initialization. [(DevToolsDaily: mermaid + React hooks)](https://www.devtoolsdaily.com/blog/integrate-mermaidjs-with-react-hooks/)
- **Calling `mermaid.initialize()` multiple times is not documented as safe.** It merges options but there is no confirmation of idempotence or clean state reset. Gate all initialization behind the module-level cached promise to call it exactly once. [(DeepWiki core API)](https://deepwiki.com/mermaid-js/mermaid/2-core-api), [(issue #5385)](https://github.com/mermaid-js/mermaid/issues/5385)
- **React StrictMode double-invokes effects** in development — the initialization guard is essential or `initialize()` runs twice. [(facebook/react #13991)](https://github.com/facebook/react/issues/13991)
- **Re-rendering an already-processed element:** if reusing a DOM node, the `data-processed` attribute must be removed before calling `mermaid.run()` / `contentLoaded()`. For `render()` (which does not touch the DOM directly), this is not an issue. [(issue #5385)](https://github.com/mermaid-js/mermaid/issues/5385)

**Open risk — theme changes between renders:**
The architecture calls for re-rendering all cards when `useUiStore.theme` changes (light/dark flip). This requires re-calling `mermaid.initialize()` with updated `themeVariables`. Whether repeated `initialize()` calls merge cleanly or corrupt state is **not confirmed in documentation**. This must be validated during implementation. If it proves unsafe, fallback: force-remount `MermaidView` on theme change (via a key prop) so each instance re-initializes from scratch.

---

## Q4: Vite / Electron dynamic import

- `import('mermaid')` in a Vite project **does** produce a separate async chunk if mermaid is not statically imported anywhere — this is the standard Vite code-splitting behavior and prevents initial-bundle inflation. [(Vite dep pre-bundling docs)](https://vite.dev/guide/dep-pre-bundling)
- **Dev mode cold start:** dynamic imports not statically discoverable by Vite may be slow to load the first time. Add `mermaid` to `optimizeDeps.include` in `vite.config.ts` to pre-bundle it during dev (this does not affect prod chunk splitting). [(Vite docs)](https://vite.dev/guide/dep-pre-bundling)
- **Electron ESM compatibility:** mermaid v10+ is ESM-only and dropped CommonJS/UMD. Early Electron versions had issues with ESM — if the project uses a recent Electron (≥ v28+, which has full ESM support) this is not a concern. Confirm the Electron version in `studio/package.json`. [(mermaid ESM discussion #4148)](https://github.com/orgs/mermaid-js/discussions/4148)
- **`contextIsolation: true` is required.** Without it, Node's ESM loader and Chromium's `import()` can conflict for dynamic ESM imports in the renderer. [(electron-vite troubleshooting)](https://electron-vite.org/guide/troubleshooting)
- **CSP:** mermaid injects inline styles into the returned SVG string. If the project enforces a strict `Content-Security-Policy` with `no unsafe-inline`, the SVG styles may be blocked. Check the Electron `BrowserWindow` CSP config before integration. [(general CSP + SVG inline styles pattern)](https://mermaid.js.org/config/usage.html)
- **If Vite pre-bundling fails for mermaid:** add `optimizeDeps.exclude: ['mermaid']` to bypass pre-bundling and let Vite serve the raw ESM. This is a documented workaround. [(vitepress-plugin-mermaid issue #83)](https://github.com/emersonbottero/vitepress-plugin-mermaid/issues/83)

---

## Q5: securityLevel

| Level | HTML allowed | Script tags | Click handlers | Notes |
|---|---|---|---|---|
| `strict` (default) | Encoded | Stripped | Disabled | Recommended minimum for untrusted input |
| `antiscript` | Allowed | Stripped | Enabled | Not adequate for untrusted input |
| `loose` | Allowed | Allowed | Enabled | Least safe — never use for untrusted input |
| `sandbox` | Via iframe | No JS execution | Disabled | Strongest isolation; breaks links/popups |

Sources: [(mermaid usage docs)](https://mermaid.js.org/config/usage.html), [(Snyk Labs: exploiting diagram renderers)](https://labs.snyk.io/resources/exploiting-diagram-renderers/)

- **`securityLevel: 'strict'` is the required minimum for AI-generated diagram source.** It prevents click-handler XSS — the primary documented attack vector (e.g., stored XSS via `click className call href "javascript:..."` in diagram source). [(Snyk Labs)](https://labs.snyk.io/resources/exploiting-diagram-renderers/)
- **`strict` alone is not sufficient for a hardened posture.** Snyk research shows `strict` has been bypassed in documented exploits. The defense-in-depth recommendation is `strict` + DOMPurify sanitization of the returned SVG string before `dangerouslySetInnerHTML` insertion, paired with a strict CSP. Given this is an Electron app (no remote untrusted code in production), `strict` is acceptable for v1 — but note the residual risk.
- **`sandbox` (iframe isolation)** is the strongest option if no interactivity (click handlers, links) is needed. The architecture's use case is display-only — `sandbox` would be safe here, but trades off against potential breakage of sequence diagram popups or other interactive features. `strict` is the pragmatic choice for v1.

---

## Key risks / open issues

| Risk | Source | Recommended action |
|---|---|---|
| **`mermaid.initialize()` called multiple times is not confirmed safe** — may corrupt theme state on light/dark flip | Q3 | Validate during implementation. Fallback: force-remount via React `key` prop on theme change |
| **`themeVariables` only accepts hex — must resolve CSS tokens to hex at runtime** | Q2 | `getComputedStyle` on `document.documentElement` is correct; confirm tokens are always resolved (not variables referencing other variables) |
| **Electron ESM compatibility** — depends on Electron version; v10+ mermaid is ESM-only | Q4 | Verify Electron version in `studio/package.json` supports ESM natively |
| **CSP inline styles in returned SVG** — mermaid SVG may contain `style` attributes | Q4 | Audit the Electron BrowserWindow CSP config; may need `unsafe-inline` for styles or a hash allow-list |
| **`strict` mode has documented bypasses** — defense-in-depth not complete without DOMPurify | Q5 | Acceptable for v1 in Electron (no remote exploit surface); document for v2 hardening |
| **`bindFunctions` interaction** — if mermaid source includes click handlers, they silently don't work under `strict`; users could be confused | Q1/Q5 | AI-generated source is unlikely to include click handlers; document the no-interactivity posture in the diagram prompt template |

---

## Sources

1. [mermaid Usage docs](https://mermaid.js.org/config/usage.html)
2. [v11.0.0 Breaking Changes Discussion #4710](https://github.com/orgs/mermaid-js/discussions/4710)
3. [renderAsync or render? Discussion #4091](https://github.com/orgs/mermaid-js/discussions/4091)
4. [Core API — DeepWiki mermaid-js](https://deepwiki.com/mermaid-js/mermaid/2-core-api)
5. [mermaid.render — Snyk Advisor](https://snyk.io/advisor/npm-package/mermaid/functions/mermaid.render)
6. [mermaid Theme Configuration](https://mermaid.ai/open-source/config/theming.html)
7. [Create custom styles — Mermaid Chart](https://mermaid.ai/docs/style-and-customize/create-custom-styles)
8. [Integrating MermaidJS with React Hooks — DevToolsDaily](https://www.devtoolsdaily.com/blog/integrate-mermaidjs-with-react-hooks/)
9. [Rendering Mermaid Diagram with errors — Issue #5385](https://github.com/mermaid-js/mermaid/issues/5385)
10. [Ben Nadel: Node Module Singleton Anti-Pattern](https://www.bennadel.com/blog/4327-caution-your-javascript-node-module-might-be-a-singleton-anti-pattern.htm)
11. [Vite Dependency Pre-Bundling](https://vite.dev/guide/dep-pre-bundling)
12. [electron-vite troubleshooting](https://electron-vite.org/guide/troubleshooting)
13. [vitepress-plugin-mermaid optimizeDeps issue #83](https://github.com/emersonbottero/vitepress-plugin-mermaid/issues/83)
14. [mermaid ESM-only Discussion #4148](https://github.com/orgs/mermaid-js/discussions/4148)
15. [Snyk Labs: Exploiting Diagram Renderers](https://labs.snyk.io/resources/exploiting-diagram-renderers/)
16. [Mermaid Security wiki](https://wiki.linux-server-admin.com/web-apps/diagramming/mermaid/security)
17. [React hooks multiple instances — facebook/react #13991](https://github.com/facebook/react/issues/13991)
