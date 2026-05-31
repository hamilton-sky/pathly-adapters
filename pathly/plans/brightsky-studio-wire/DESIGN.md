# Design System — brightsky-studio-wire

> Stack: React (CSS Modules, no Tailwind — matches existing codebase) · 2026-05-31

## Query

Electron desktop developer tool chat panel with AI thinking indicator, tool call status display, and AI automation progress feedback. Dark mode. Minimalist style.

---

## 1. Design System Summary

### Palette — uses existing `tokens.css` variables, no new root tokens required

| Token | Dark Default | Role |
|---|---|---|
| `--bg-base` | `#111827` | Panel background |
| `--bg-surface0` | `#1E2433` | Card / block background |
| `--bg-surface1` | `#283044` | Elevated surface, active step |
| `--accent` | `#38BDF8` | Brightsky primary (sky blue) |
| `--green` | `#34D399` | Success / step complete |
| `--yellow` | `#FCD34D` | Warning / tool waiting |
| `--red` | `#F87171` | Error / tool failed |
| `--runtime` | `#2DD4BF` | Automation in progress (teal) |
| `--text-primary` | `#E2E8F0` | Body text |
| `--text-secondary` | `#94A3B8` | Labels, phase text |
| `--text-muted` | `#64748B` | Timestamps, source URLs |
| `--border` | `1px solid #283044` | Card borders |
| `--border-subtle` | `1px solid #1E2433` | Dividers |

**New feature-scoped tokens** — add to a `BrightskyStates.module.css` or inline via `useTheme()`:

```css
/* Animation durations */
--bs-pulse-duration: 1.6s;
--bs-dot-delay-step: 0.22s;
--bs-fade-in: 180ms ease-out;
--bs-transition-base: 150ms ease-out;

/* Semantic surface for Brightsky-specific elements */
--bs-thinking-border: rgba(56, 189, 248, 0.25);  /* accent at 25% */
--bs-thinking-bg:     rgba(56, 189, 248, 0.06);
--bs-tool-border:     rgba(252, 211, 77, 0.30);   /* yellow at 30% */
--bs-tool-bg:         rgba(252, 211, 77, 0.07);
--bs-tool-error-border: rgba(248, 113, 113, 0.35);
--bs-tool-error-bg:     rgba(248, 113, 113, 0.08);
--bs-auto-border:     rgba(45, 212, 191, 0.30);   /* runtime at 30% */
--bs-auto-bg:         rgba(45, 212, 191, 0.07);
```

### Typography

All Brightsky status elements use the existing font stack. No new fonts.

| Role | Size | Weight | Color token |
|---|---|---|---|
| Phase label ("Analyzing your plan…") | 12px | 500 | `--text-secondary` |
| Tool name ("get_feature_plan") | 11px | 600 | `--accent` (thinking), `--yellow` (waiting), `--red` (error) |
| Tool monospace call detail | 11px | 400 | `--text-muted`, `font-family: var(--font-family-mono)` |
| Automation step label | 12px | 400 | `--text-primary` |
| Citation URL | 11px | 400 | `--text-muted` |
| Citation chip label | 11px | 500 | `--accent` |

### Motion tokens

| Token | Value | Used for |
|---|---|---|
| `--bs-pulse-duration` | `1.6s` | Thinking indicator pulse ring |
| `--bs-dot-delay-step` | `0.22s` | Staggered dot animation |
| `--bs-fade-in` | `180ms ease-out` | Element enter |
| `dotBounce` | existing keyframe | Reuse from `MessageList.module.css` |
| `pulse` | new keyframe (below) | Icon pulse ring |
| `shimmer` | new keyframe (below) | Tool row left-border animation |

New keyframes to add (in the relevant module CSS):

```css
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0px rgba(56, 189, 248, 0.50); }
  70%  { box-shadow: 0 0 0 6px rgba(56, 189, 248, 0); }
  100% { box-shadow: 0 0 0 0px rgba(56, 189, 248, 0); }
}

@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}

@prefers-reduced-motion {
  .pulseDot,
  .thinkingPhaseDot,
  .shimmerBorder { animation: none; }
}
```

---

## 2. Component Specifications

### 2A. ThinkingPhaseRow — "Analyzing your plan…" indicator

**Trigger:** `typing_metadata` WebSocket event arrives, backend is reasoning before streaming.

**Placement:** Inline, immediately below the role badge (`Conductor`) of the in-progress assistant message. Replaces the existing `ThinkingDots` + `StreamingTimer` pair when the model is Brightsky. Disappears when `stream_chunk` events begin arriving (first token received).

**Layout:**

```
[ • ] Analyzing your plan…               12s
```

- Left: 8px pulsing dot, color `--accent`, animation `pulse var(--bs-pulse-duration) infinite`
- Middle: phase label text, `--text-secondary`, 12px, italic, updates in place as `typing_metadata` events arrive
- Right: elapsed timer (reuse `StreamingTimer` logic), `--text-muted`, 11px, tabular-nums

**Container:**

```css
.thinkingPhaseRow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0 5px 2px;
  animation: fadeIn var(--bs-fade-in);
}

.thinkingPhaseDot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  animation: pulse var(--bs-pulse-duration) infinite;
}

.thinkingPhaseLabel {
  font-size: 12px;
  font-style: italic;
  color: var(--text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

**States:**

| State | Dot | Label |
|---|---|---|
| `typing_metadata` active | Pulsing `--accent` | Phase text (e.g. "Analyzing your plan…") |
| `stream_chunk` first token | Fade out (200ms) entire row | Hidden |
| `stream_end` | Hidden | Hidden |
| `prefers-reduced-motion` | Static dot, no pulse | Static |

**Transition to streaming:** when the first `stream_chunk` arrives, animate the `ThinkingPhaseRow` out (`opacity: 0`, `max-height: 0`, 200ms) before the text content begins rendering. Do not abruptly remove it.

**Accessibility:**
- Wrap in `<div role="status" aria-live="polite" aria-label="AI is thinking">` so screen readers announce phase changes.
- Only the label text should be in the live region — not the timer (it changes every second and would be too noisy).

---

### 2B. ToolCallRow — "Using tool: get_feature_plan…"

**Trigger:** `tool_call` WebSocket event. Remains visible until matching `tool_response` arrives.

**Placement:** Inline in the message list as a distinct row type, not a full message bubble. Rendered between the last partial streaming text and the next content. Multiple ToolCallRows can stack if the backend calls tools sequentially.

**Layout (pending):**

```
[ spinner ] get_feature_plan              waiting…
  read(feature: brightsky-studio-wire)
```

**Layout (success):**

```
[ check  ] get_feature_plan              12ms
  read(feature: brightsky-studio-wire)
```

**Layout (error):**

```
[ x mark ] get_feature_plan              failed
  Error: plan not found
```

**Container:**

```css
.toolCallRow {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  border-radius: 4px;
  border-left: 2px solid var(--bs-tool-border);
  background: var(--bs-tool-bg);
  margin: 2px 0;
  animation: fadeIn var(--bs-fade-in);
}

.toolCallRow.success {
  border-left-color: rgba(52, 211, 153, 0.40);  /* green */
  background: rgba(52, 211, 153, 0.06);
}

.toolCallRow.error {
  border-left-color: var(--bs-tool-error-border);
  background: var(--bs-tool-error-bg);
}

.toolCallHeader {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toolCallIcon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* pending: accent, success: green, error: red */
.toolCallName {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);    /* overridden per state below */
  flex: 1;
  font-family: var(--font-family-mono);
}

.toolCallStatus {
  font-size: 10px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.toolCallDetail {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-family-mono);
  padding-left: 20px;
  line-height: 1.4;
}
```

**States and icon mapping:**

| State | Left icon (Lucide) | Name color | Status text |
|---|---|---|---|
| pending | `Loader2` (spinning, 14px) | `--accent` | "waiting…" |
| success | `CheckCircle` (14px, `--green`) | `--text-secondary` | duration e.g. "43ms" |
| error | `XCircle` (14px, `--red`) | `--red` | "failed" |

**Accessibility:**
- Wrap all ToolCallRows in a `<div role="log" aria-label="Tool activity" aria-live="assertive">` container.
- Each row: `aria-label="Tool {name} {status}"`.
- On error: `aria-invalid="true"` on the row.

**Do not** collapse or remove ToolCallRows after success — keep them visible as a trace until the full message is marked done (status `stream_end`). After `stream_end`, they may collapse to a single summary line: "3 tools used".

---

### 2C. AutomationBanner — "AI is controlling the wizard"

**Trigger:** `tool_call` event where `tool_name` matches `automation:executeStep`. This is distinct from a data-fetch tool call.

**Placement:** Persistent sticky banner at the top of the `MessageList` scroll area (not in the chat header — keeping the header stable). The banner covers the full panel width minus the 12px padding on each side. It is fixed to the top of the `.list` scroll container using `position: sticky; top: 0; z-index: 10`.

**Layout:**

```
+--------------------------------------------------+
| [teal dot]  AI is controlling the wizard         |
|  Step 3 of 7:  Filled "Feature name" input       |
|             [Cancel]  [Pause]                    |
+--------------------------------------------------+
```

**Container:**

```css
.automationBanner {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1.5px solid var(--bs-auto-border);
  background: var(--bs-auto-bg);
  margin-bottom: 8px;
  animation: fadeIn var(--bs-fade-in);
}

.automationBannerTitle {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 600;
  color: var(--runtime);
}

.automationBannerDot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--runtime);
  animation: pulse 1.6s infinite;
}

.automationBannerStep {
  font-size: 11px;
  color: var(--text-secondary);
  padding-left: 14px;
}

.automationBannerActions {
  display: flex;
  gap: 6px;
  padding-left: 14px;
  margin-top: 2px;
}
```

**Step log** — beneath the banner title, show the last completed step as greyed text and the current step as active:

```
  Step 2/7  [check]  Clicked "New Feature" button
  Step 3/7  [teal dot]  Filling "Feature name" input…
```

Limit visible step log to the last 3 entries. Older entries drop out of view (no scrollbar — the banner should not grow tall).

**Staged mode (user must approve each step):**

When `automationStore.mode === 'staged'`, the current step row shows inline Approve / Skip buttons (reuse existing `AutomationCard` button styles). The banner title changes to "AI waiting for approval".

**Cancel button** — calls `automationStore.setStatus('idle')` and sends a `stop_generation` WebSocket message. The banner fades out.

**Accessibility:**
- `role="alert"` on the banner — announces when automation starts.
- `aria-live="assertive"` for the step log (each new step is announced).
- Cancel button: `aria-label="Cancel AI automation"`.

---

### 2D. CitationChips — source URLs below a message

**Trigger:** Backend response includes a `sources` array alongside the message content.

**Placement:** Rendered below the message `.content` span, before the next message. Part of the same message row.

**Layout (collapsed, default):**

```
[ Sources (3) v ]
```

**Layout (expanded):**

```
[ Sources (3) ^ ]
  [1] pathly.dev/docs/pipeline         [2] github.com/…
  [3] brightsky.ai/api-reference
```

**Implementation:**

```css
.citationToggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 2px 7px;
  border-radius: 10px;
  border: 1px solid var(--accent-border);
  background: var(--accent-bg);
  font-size: 10px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
  transition: background var(--transition-base);
}

.citationToggle:hover {
  background: rgba(56, 189, 248, 0.15);
}

.citationList {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 5px;
  animation: fadeIn var(--bs-fade-in);
}

.citationChip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-surface0);
  border: 1px solid var(--border);
  font-size: 10px;
  color: var(--text-muted);
  cursor: pointer;
  text-decoration: none;
  transition: border-color var(--transition-base), color var(--transition-base);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citationChip:hover {
  border-color: var(--accent-border);
  color: var(--accent);
}
```

**Accessibility:**
- Toggle: `aria-expanded`, `aria-controls="citations-{msgId}"`.
- Each chip: `<a href={url} target="_blank" rel="noopener noreferrer" aria-label="Source: {domain}">`.
- Citation list: `role="list"`, each chip: `role="listitem"`.

---

### 2E. ConnectionBadge — refined states

The existing badge in `ConductorHeader` shows `● live / ● syncing / ○ offline`. Three new Brightsky-specific sub-states need visual distinction without adding new badge variants:

| State | Badge | Color | When |
|---|---|---|---|
| `offline` | `○ offline` | `--text-muted` | No WebSocket connection |
| `connecting` | `◌ connecting` | `--yellow` (pulse) | `ws.readyState === CONNECTING` |
| `live` | `● live` | `--green` | Connected, idle |
| `thinking` | `● thinking` | `--accent` (pulse) | `typing_metadata` active |
| `streaming` | `● streaming` | `--accent` (solid) | `stream_chunk` arriving |
| `tool` | `◈ tool` | `--yellow` | `tool_call` pending response |
| `automating` | `● automating` | `--runtime` (pulse) | `automation:executeStep` active |

Implementation: a single `status` prop on `ConductorHeader` (string union). The badge dot gets an `animation: pulse` class when the state is `thinking` or `automating`. The icon character changes for `tool` and `connecting`. No layout changes to the header — this is a single pill element update.

```css
.connectionBadge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 8px;
  background: var(--bg-surface0);
  border: var(--border-subtle);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
  transition: color var(--bs-transition-base), background var(--bs-transition-base);
}

.connectionDot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.connectionDot.pulsing {
  animation: pulse var(--bs-pulse-duration) infinite;
}
```

---

### 2F. Message type visual differentiation

All message types appear inside the existing `.message` container with a role badge. The badge text and color distinguishes type:

| Message type | Badge text | Badge background | Badge text color | Left accent border |
|---|---|---|---|---|
| Regular AI answer | `Conductor` | `accent + 22` (existing) | `--accent` | none |
| Plan-aware AI answer | `Conductor · Plan` | `accent + 22` | `--accent` | none (use a pin icon instead — see below) |
| Tool call row | (no badge — it's inline, not a bubble) | — | — | `--yellow` at 25% |
| Automation step | (no badge — inline in AutomationBanner) | — | — | — |

**Plan-aware messages** — when the backend sends a message that references a specific story or plan file, append a small pill below the message content:

```
[ plan-icon  brightsky-studio-wire / USER_STORIES.md ]
```

```css
.planRefChip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 2px 7px;
  border-radius: 10px;
  background: var(--bg-surface0);
  border: 1px solid var(--border);
  font-size: 10px;
  color: var(--text-muted);
}
```

---

## 3. CSS class reference (builder lookup table)

| Element | Class name | File |
|---|---|---|
| Thinking phase row | `.thinkingPhaseRow` | `BrightskyStates.module.css` (new) |
| Thinking phase dot | `.thinkingPhaseDot` | `BrightskyStates.module.css` |
| Thinking phase label | `.thinkingPhaseLabel` | `BrightskyStates.module.css` |
| Tool call row | `.toolCallRow` | `BrightskyStates.module.css` |
| Tool call row (success) | `.toolCallRow.success` | `BrightskyStates.module.css` |
| Tool call row (error) | `.toolCallRow.error` | `BrightskyStates.module.css` |
| Tool call header | `.toolCallHeader` | `BrightskyStates.module.css` |
| Tool call name | `.toolCallName` | `BrightskyStates.module.css` |
| Tool call detail | `.toolCallDetail` | `BrightskyStates.module.css` |
| Tool call status | `.toolCallStatus` | `BrightskyStates.module.css` |
| Automation banner | `.automationBanner` | `BrightskyStates.module.css` |
| Automation banner title | `.automationBannerTitle` | `BrightskyStates.module.css` |
| Automation banner dot | `.automationBannerDot` | `BrightskyStates.module.css` |
| Automation step log | `.automationBannerStep` | `BrightskyStates.module.css` |
| Automation actions | `.automationBannerActions` | `BrightskyStates.module.css` |
| Citation toggle | `.citationToggle` | `BrightskyStates.module.css` |
| Citation list | `.citationList` | `BrightskyStates.module.css` |
| Citation chip | `.citationChip` | `BrightskyStates.module.css` |
| Connection badge | `.connectionBadge` | `ConductorHeader.module.css` (extend) |
| Connection dot | `.connectionDot` | `ConductorHeader.module.css` (extend) |
| Connection dot pulsing | `.connectionDot.pulsing` | `ConductorHeader.module.css` (extend) |
| Plan ref chip | `.planRefChip` | `BrightskyStates.module.css` |

All new classes go in a single new file: `studio/src/renderer/src/components/ChatPanel/BrightskyStates.module.css`

---

## 4. Accessibility requirements

| Requirement | Implementation |
|---|---|
| Thinking phase live region | `<div role="status" aria-live="polite">` wrapping `ThinkingPhaseRow` |
| Tool activity live region | `<div role="log" aria-live="assertive" aria-label="Tool activity">` wrapping all `ToolCallRow` elements |
| Automation banner | `role="alert"` on first render; `aria-live="assertive"` for step updates |
| Cancel / Pause buttons | Minimum 32px touch target height; explicit `aria-label` |
| Citations | `aria-expanded` on toggle; `role="list"` on chip container |
| Animations | All pulse and bounce animations wrapped in `@media (prefers-reduced-motion: reduce)` to set `animation: none` |
| Connection badge | `aria-label="Connection status: {state}"` on the badge element |
| Focus ring | Reuse existing `--focus-ring: 2px solid var(--accent)` on all interactive elements |
| Contrast | All new text against its background clears 4.5:1. `--text-secondary` (#94A3B8) on `--bg-surface0` (#1E2433) = 6.1:1. `--accent` (#38BDF8) on `--bg-surface0` = 5.4:1. |

---

## 5. Do / Don't rules

### Thinking indicator
- **Do:** Show `ThinkingPhaseRow` immediately on `typing_metadata`. Update label in-place as new events arrive.
- **Do:** Transition smoothly out when first `stream_chunk` token arrives (200ms fade + height collapse).
- **Don't:** Keep the row visible while content is streaming — it creates visual noise alongside the token stream.
- **Don't:** Use a full-width spinner or modal overlay — this is a tool panel, the user needs to see surrounding context.

### Tool call rows
- **Do:** Render tool calls inline, stackable, inside the message flow. They are part of the AI's reasoning chain.
- **Do:** Keep completed tool calls visible until `stream_end` — they give the user confidence the AI checked the right data.
- **Do:** After `stream_end`, collapse the stack to a single "N tools used" summary line (toggle to expand).
- **Don't:** Use a toast or snackbar for tool calls — they disappear before the user can register what was called.
- **Don't:** Show raw JSON payloads by default — show only the tool name and the key parameter (e.g. feature name).

### Automation banner
- **Do:** Make the banner sticky at the top of the message list so it stays visible even when messages scroll.
- **Do:** Show only the last 2–3 steps in the banner step log. Too many items make the banner grow vertically.
- **Do:** Offer both Cancel (stops immediately) and Pause (waits for the current step to finish) in staged mode.
- **Don't:** Place the banner in the chat header — the header is compact and contains nav controls; mixing automation state into it creates confusion.
- **Don't:** Auto-approve steps silently in staged mode — each step must have a visible approve/skip affordance.

### Citations
- **Do:** Default to collapsed. Most users don't need to see sources on every message.
- **Do:** Truncate long URLs to the domain + first path segment only.
- **Don't:** Render citations as raw URLs in the message body text — they break line flow.
- **Don't:** Open links in the Electron main window — always use `shell.openExternal` (IPC) or `target="_blank"`.

### Connection badge
- **Do:** Pulse the dot (not the full badge) during `thinking` and `automating` states.
- **Don't:** Change the badge size or layout on state transitions — it will shift surrounding header elements.
- **Don't:** Cycle through the full state list in a way the user cannot pause — the badge is informational, not interactive.

---

## 6. ASCII mockup — chat panel full state

The panel is 320–400px wide. Column width shown as fixed characters.

```
┌─────────────────────────────────────────────────────────┐
│ ⚡ HQ   [claude ●] [codex] [shell]   [+] [⊞] [×]       │
│                              ● thinking                  │
├─────────────────────────────────────────────────────────┤
│  [CONTROLS ▶]  [PIPELINE ▼]                             │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐   │
│  │ [~] AI is controlling the wizard      [Pause][X] │   │  <-- AutomationBanner (sticky top)
│  │  Step 2/7 [✓] Clicked "New Feature"             │   │
│  │  Step 3/7 [•] Filling "Feature name" input…     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  YOU                                                    │
│  Add a storm phase to the brightsky feature             │
│                                                         │
│  CONDUCTOR                                              │
│  • Analyzing your plan…                          12s   │  <-- ThinkingPhaseRow (active)
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ [⟳] get_feature_plan                  waiting…  │   │  <-- ToolCallRow (pending)
│  │     read(feature: brightsky-studio-wire)         │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ [✓] list_user_stories                    43ms    │   │  <-- ToolCallRow (success)
│  │     read(filter: storm)                          │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ├───────────────────── next message ─────────────────  │
│                                                         │
│  CONDUCTOR · Plan                                       │
│  Here are the storm stories I found for this feature.   │
│  You can add a new one by clicking the board below.     │
│                                                         │
│  [plan-icon  brightsky-studio-wire / USER_STORIES.md]  │  <-- PlanRefChip
│  [ Sources (2) ▼ ]                                     │  <-- CitationToggle (collapsed)
│                                                         │
│  ── expanded state below ────────────────────────────── │
│  [ Sources (2) ▲ ]                                     │
│  [ [1] brightsky.ai/docs ]  [ [2] pathly.dev/guide ]  │  <-- CitationChips
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [ Ask Conductor anything…          ] [↑] [■ stop]      │
└─────────────────────────────────────────────────────────┘


STATE LEGEND
──────────────────────────────────────────────────
[•]  pulsing teal dot    = automation active
[•]  pulsing sky-blue    = thinking active
[⟳]  spinning Loader2    = tool call pending
[✓]  CheckCircle green   = tool call success
[✗]  XCircle red         = tool call error
[~]  teal shimmer border = automation banner
──────────────────────────────────────────────────


SECONDARY STATE: Tool error
  ┌──────────────────────────────────────────────────┐
  │ [✗] get_feature_plan                    failed   │   border-left: red 25%
  │     Error: feature not found                     │   color: --red
  └──────────────────────────────────────────────────┘


SECONDARY STATE: Post-stream tool summary (collapsed)
  [ 3 tools used ▼ ]                                    <-- replaces ToolCallRows after stream_end
  ── expanded ───────────────────────────────────────
  [ ✓ get_feature_plan ]  [ ✓ list_user_stories ]
  [ ✓ automation:executeStep ]


SECONDARY STATE: Automation staged mode (awaiting approval)
  ┌──────────────────────────────────────────────────┐
  │ [~] AI waiting for approval           [Cancel]   │
  │  Step 4/7:  Click "Add Story" button             │
  │             [✓ Approve]  [→ Skip]                │
  └──────────────────────────────────────────────────┘


SECONDARY STATE: Connection offline
  ──────────────────────────────────────
  ○ offline                                             <-- badge in header, grey
  ──────────────────────────────────────
  [Retry connection]                                    <-- shown in empty message area
```

---

## Builder Notes

- Reference `tokens.css` for all color values — do not hardcode hex in component files.
- Create `BrightskyStates.module.css` as the single new file for all Brightsky-specific CSS classes listed in Section 3.
- The `ThinkingPhaseRow` component should replace the existing `ThinkingDots` + `StreamingTimer` pair when `useModelStore.getState().selectedModelId === 'brightsky'`. Keep the existing components for local LLM modes.
- `ToolCallRow` and `CitationChips` are new components. Place them in `studio/src/renderer/src/components/ChatPanel/`.
- `AutomationBanner` extends the existing automation pattern. It is a new component separate from `AutomationCard` and `StepQueue`, which handle the local automation flow. Brightsky automation uses the WebSocket `automation:executeStep` tool call, not the existing `automationStore` plan.
- The `ConnectionBadge` extension belongs in `ConductorHeader.tsx` — add a `brightskyStatus` prop of type `'offline' | 'connecting' | 'live' | 'thinking' | 'streaming' | 'tool' | 'automating'` and derive badge appearance from it.
- All new animations must be gated behind `@media (prefers-reduced-motion: reduce)`.
- Stack: React with CSS Modules (this codebase does not use Tailwind — CSS class specs above use CSS Modules syntax).
```
