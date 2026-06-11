# Command Center — Porting Map (kit → Studio)

**Purpose:** turn the `src/` reference kit into production Studio components, conforming to
`studio/CLAUDE.md` (UI rules), `studio/src/renderer/src/styles/tokens.css` (theme tokens), and
`comms-board/UI-DIRECTION.md §7` (target structure). Read those three first.

> The kit is a faithful **reference**, not a drop-in. Copying files verbatim trips Studio's
> lint/structure rules immediately (inline styles, monolithic CSS, flat files). Port
> component-by-component using the transforms below.

---

## 0. Headline — how aligned is it already?

| Dimension | State |
|---|---|
| Stack | React 18 ✅ · `zustand` ✅ · `lucide-react` ✅ · `marked` ✅ · Geist Mono ✅ |
| Tokens | Uses Studio's **exact** semantic tokens (`--bg-*`, `--accent`, `--state-*`, `--radius-*`, `--font-*`). |
| Theming | **Free multi-theme** (all 11 themes) after the one token gap below — no hardcoded palette. |
| Color system | Agent/stage colors already map to `--state-*` pipeline tokens (`agents.ts`). |
| Gaps | `--orange-bg`/`--orange-border` undefined · 6× raw `#fff` · inline styles · 1 monolith CSS · context store · seed data. |

So the **design, visual system, interaction model, and token vocabulary are done**. What remains
is mechanical conformance + backend wiring.

---

## 1. Destination roots

```
studio/src/renderer/src/
  components/HQ/CommsPanel/        ← reusable board-thread building block
  components/HQ/CommandCenter/     ← the workspace shell
  store/commsStore.ts             ← zustand (mirror chatStore.ts) — data
  store/commandCenterStore.ts     ← zustand + persist — layout
```

Per `CLAUDE.md` folder rule: every `.tsx` gets a co-located `.module.css`; hooks live in a
`hooks/` subfolder; ~150-line hard cap per file; shared icons in a flat `icons.tsx`.

---

## 2. Per-file mapping

| Kit file (`src/`) | Studio destination | Transform |
|---|---|---|
| `types.ts` | `HQ/CommandCenter/types.ts` | **Direct reuse.** Already mirrors SPEC §5; align field names to the `GET /comms` payload when wiring. |
| `agents.ts` | `HQ/CommandCenter/constants.ts` | Keep `AGENTS`/`STAGE_COLOR`/`SCOPES`/`COMPOSE_TYPES` metadata. **Color strings stop being inline** — see §3 (→ `data-stage`/`data-agent` + CSS). |
| `Icon.tsx` | **delete** | Replace `window.PathlyIcons` with direct `lucide-react` imports. Consumers import named glyphs; no wrapper. |
| `seed.ts` | **delete** (keep as vitest fixture) | Replaced by live data — hydrate the store from `GET /comms`. |
| `useCommsStore.tsx` | `store/commsStore.ts` | Context → **zustand** (`chatStore.ts` pattern). **Logic reused verbatim** (`post/answer/resolve/pendingCount/messagesFor`); wire actions to endpoints (§4). |
| `useCommandCenter.ts` | `store/commandCenterStore.ts` | → zustand + `persist` middleware (`localStorage: pathly-command-center-layout`). Presets/direction/accordion/set-main logic reused. |
| `useCommsPanel.ts` | `HQ/CommsPanel/hooks/useCommsPanel.ts` | Reuse; swap mock flash for the real `COMMS_UPDATE` SSE subscription (§4). |
| `useSectionResize.ts` | `HQ/CommandCenter/hooks/useSectionResize.ts` | Reuse drag math. **Add keyboard a11y** (arrow-key resize, `role="separator"`, `aria-orientation`). Set `MIN` to match the spec (see §6). |
| `CommandCenter.tsx` | `HQ/CommandCenter/CommandCenter.tsx` + `.module.css` | Reuse layout. Remove inline `style`; class names → CSS module. |
| `CommandCenterHeader.tsx` | `HQ/CommandCenter/CommandCenterHeader.tsx` + css | `type="button"` on all; `aria-pressed` on section tabs; `aria-expanded`/`aria-haspopup` on the presets menu. |
| `FeatureSidebar.tsx` | `HQ/CommandCenter/FeatureSidebar.tsx` + css | `aria-expanded` on the collapse toggle; rail buttons `aria-label`. |
| `FeatureCard.tsx` | `HQ/CommandCenter/FeatureCard.tsx` + css | Inline `STAGE_COLOR` → `data-stage` (§3). "Main feature" inline chip → `.mainChip` class. Accordion bar → `<button aria-expanded>`. |
| `BoardSection.tsx` | `HQ/CommandCenter/BoardSection.tsx` + css | `bs-icon` inline color → `.bsIcon` class. `flexStyle()` → inject a CSS var `style={{'--section-flex': w} as CSSProperties}` feeding `flex: var(--section-flex)` (the allowed CLAUDE.md exception). |
| `CommsPanel.tsx` | `HQ/CommsPanel/CommsPanel.tsx` + css | Reuse. Read-scope checkboxes → `type="button"` + `aria-pressed` (or real `<input type=checkbox>`). |
| `CommsMsgList.tsx` | `HQ/CommsPanel/CommsMsgList.tsx` + css | Reuse pinned-decisions tray + thread. Borrow virtualization/scroll patterns from `HQ/MessageList`. |
| `CommsMsgCard.tsx` | `HQ/CommsPanel/CommsMsgCard.tsx` + css | **`dangerouslySetInnerHTML` → `<MarkdownRenderer>`** (`shared/MarkdownRenderer`). Inline `STAGE_COLOR` → `data-stage`. If >150 lines, split `CardBody` variants (question/warning/artifact) into sibling files. |
| `CommsInput.tsx` | `HQ/CommsPanel/CommsInput.tsx` + css | `type="button"` on type-picker + send. Keep ⌘/Ctrl+Enter. |
| `MessageTypeBadge.tsx` | `HQ/CommsPanel/MessageTypeBadge.tsx` + css | `data-type` chip. Tints come from tokens — **needs `--orange-bg` (§5)**. |
| `Avatar.tsx` | `HQ/CommsPanel/Avatar.tsx` + css | Agent glyph; `AGENTS.color` → `data-agent` (§3). `#fff` on "you" gradient → keep or tokenize (§5). |
| `command-center.css` | **split** → one `*.module.css` per component | De-globalize class names (`.cc`, `.msg`, `.feat` → local). Rules port ~verbatim; only selectors change. |
| `index.tsx` | **delete** | Studio mounts `<CommandCenter/>` into the HQ shell, not a standalone root. |
| `preview.html` | keep in kit only | Not ported. |

---

## 3. Global transform — inline color → `data-*` + tokens (CLAUDE.md non-negotiable)

`CLAUDE.md`: *"Never use `style={{}}`. Theme colors always come from CSS custom properties."*
Plus the *"data attributes over class proliferation"* rule. So every `style={{ color: STAGE_COLOR[...] }}`
becomes a `data-*` attribute the CSS module resolves to a **token**:

```tsx
// kit:   <span style={{ color: STAGE_COLOR[stage] }}>{stage}</span>
// studio:<span className={s.stage} data-stage={stage}>{stage}</span>
```
```css
.stage[data-stage='PLANNING']  { color: var(--state-planning); }
.stage[data-stage='BUILDING']  { color: var(--state-building); }
.stage[data-stage='REVIEWING'] { color: var(--state-reviewing); }
.stage[data-stage='TESTING']   { color: var(--state-testing); }
.stage[data-stage='RETRO']     { color: var(--state-retro); }
.stage[data-stage='DONE']      { color: var(--state-done); }
```

Same pattern for `data-agent` (avatars) and `data-status` (feature status dots), all resolving
to existing tokens. This is the bulk of the inline-style removal and it keeps full theme support.

---

## 4. Data wiring — store actions → backend (replaces `seed.ts`)

| Store action (kit) | Backend (SPEC §10) | Note |
|---|---|---|
| hydrate `features` + `boards` | `GET /comms?feature=&board=` | one fetch per visible scope on mount |
| `post(key,type,text)` | `POST /comms/post` | optimistic append, reconcile on echo |
| `answer(fid,mid,opt)` | `POST /comms/answer` | |
| `resolve(mid, block\|note\|ignore)` | `POST /comms/acknowledge` (+ `POST /comms/post` decision on `note`) | mirrors SPEC §9 flow |
| `toggleScope(fid,scope)` | board_scope set | ⚠ **gap:** Phase-1 added `get/set_board_scope` query helpers but verify an HTTP route exists; add `POST /comms/scope` if not. |
| live updates | `GET /events/comms?scope=` (SSE `COMMS_UPDATE`) | subscribe in `useCommsPanel`; route to `commsStore.appendMessage` (mirror `runnerStore` SSE wiring + add `comms_update` to `NotifCategory`). |

---

## 5. Token alignment — required `tokens.css` change

The kit references two tokens that **do not exist** (`grep` → 0 hits). Add to `:root` in
`tokens.css`, beside the `--orange` signal hue (it is not themed, so `:root`-only is consistent
with the existing `--red-bg`/`--red-border` convention):

```css
/* Reviewing / warning surface — parity with --red-bg / --red-border */
--orange-bg:     rgba(249, 115, 22, 0.13);
--orange-border: rgba(249, 115, 22, 0.40);
```

**Minor (optional):** 6× `color: #fff` on accent-filled buttons/chips (`command-center.css`
L124,125,139,198,290,312). Acceptable as-is (accents are dark enough for white text across all
themes), but for strict compliance add `--text-on-accent: #fff;` and reference it.

Everything else the kit uses is already defined — no other token work.

---

## 6. Spec reconciliation (carry over from the kit review)

- **Min section size:** `useSectionResize` `MIN = 220` vs `UI-DIRECTION §4` `280`. Pick one — recommend bending the spec to **220** (the implementer's deliberate value). Update whichever you keep.
- **Initial preset:** kit's `INITIAL` is `preset:'focus'` with an expanded sidebar, but `PRESETS.focus` collapses it → relabel initial to `'pipeline'`.
- **Board section order:** board-view renders widest panel (feature 50%) rightmost. Open design question (feature-first / center?) — left as-is unless you decide otherwise.

---

## 7. Reuse these existing Studio assets (don't rebuild)

| Need | Use |
|---|---|
| Render message text | `shared/MarkdownRenderer/MarkdownRenderer.tsx` |
| Thread list patterns | `HQ/MessageList/` |
| zustand store shape | `store/chatStore.ts` |
| SSE → store wiring | `store/runnerStore.ts` + the runner SSE handler |
| Theme tokens (11 themes) | `styles/tokens.css` |
| Icons | `lucide-react` |

---

## 8. Suggested port order

1. **`tokens.css`** — add `--orange-bg`/`--orange-border` (§5). One-line unblock; everything else renders correctly after.
2. **`types.ts` + `constants.ts`** — pure data, no deps.
3. **`store/commsStore.ts` + `commandCenterStore.ts`** — zustand, still on seed data, verify logic.
4. **`CommsPanel/` leaf components** — Avatar, MessageTypeBadge, CommsMsgCard, CommsMsgList, CommsInput, CommsPanel (+ split CSS, `data-*`, `MarkdownRenderer`).
5. **`CommandCenter/` shell** — BoardSection, FeatureCard, FeatureSidebar, Header, CommandCenter, resize hook.
6. **Data wiring (§4)** — swap seed → `GET /comms` + SSE; add board_scope route if missing.
7. **a11y + `type="button"` + tests** (vitest).

Step 1 alone makes the kit render pixel-correct under Studio's themes; steps 2–5 are the
component port; 6 turns it live.
