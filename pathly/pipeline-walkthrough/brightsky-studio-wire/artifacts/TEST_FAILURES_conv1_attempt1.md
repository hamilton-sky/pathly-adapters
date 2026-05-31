# TEST_FAILURES — brightsky-studio-wire

Generated: 2026-05-31

---

## FAIL 1 — S-03: Capability handshake declares `canExecuteToolCalls: true`, not `false`

**Criterion:** In Conv 1 the handshake declares `canExecuteToolCalls: false` and `canStreamThinking: true`

**File:** `studio/src/renderer/src/lib/brightskyClient.ts` line 74

**Expected:** `canExecuteToolCalls: false`

**Actual:** `canExecuteToolCalls: true`

The `client_capabilities` message sent after `session_created` sets `canExecuteToolCalls: true`. The user story specifies `false` for Conv 1 (tool execution capability was to be added in Conv 3).

```ts
// current (line 72-78)
capabilities: {
  canAnalyzeDom: false,
  canExecuteToolCalls: true,   // <-- should be false per S-03
  canStreamThinking: true,
  supportedToolTypes: ['studio_analyzer', 'automation'],
},
```

---

## FAIL 2 — S-08: `InlineCreateInput` plan-folder instance has wrong `data-label`

**Criterion:** `sidebar/shared/InlineCreateInput.tsx` — plan name input has `data-label="New Plan Name"` (primary feature-creation target)

**File:** `studio/src/renderer/src/components/sidebar/shared/InlineCreateInput.tsx` line 32
**Call site:** `studio/src/renderer/src/components/sidebar/items/PlanSection.tsx` line 98-102

**Expected:** When the plan-folder inline input is shown, the input element has `data-label="New Plan Name"`

**Actual:** PlanSection calls `<InlineCreateInput type="folder" .../>`. The component sets:
```ts
data-label={type === 'folder' ? 'New Folder Name' : 'New Plan Name'}
```
So when creating a plan folder the rendered `data-label` is `"New Folder Name"`, not `"New Plan Name"`.

This is the primary AI target for feature creation (S-07 criterion 1 depends on `action: 'fill', label: 'New Plan Name'`). The AI's `automation:executeStep` call would fail to find the element.

**Fix options:**
- Pass a `label` prop to `InlineCreateInput` so PlanSection can override the data-label for the plan-folder case
- Or use a dedicated prop `data-label="New Plan Name"` when `target === 'plan-folder'`

---

## FAIL 3 — S-08: BottomNav panel buttons missing `data-label`

**Criterion:** App-level navigation panels (Monitor, Chat, Files, Terminal) have `data-label` matching panel name

**File:** `studio/src/renderer/src/components/sidebar/shell/BottomNav.tsx`

**Expected:** Monitor and Settings navigation buttons have `data-label="Monitor"` and `data-label="Settings"` respectively

**Actual:** Both buttons use `data-testid` (not `data-label`) and have no `data-label` attribute:
```tsx
<button data-testid="sidebar-nav-monitor" ...>Monitor</button>
<button data-testid="sidebar-nav-settings" ...>Settings</button>
```

Additionally, the Chat panel toggle (in `ChatHeader` or elsewhere) and any Files/Terminal navigation buttons were not found to have `data-label` attributes.

---

## FAIL 4 — S-08: `ConfigForm.tsx` missing `data-label` on model and category selects

**Criterion:** `Editor/ConfigForm.tsx` — name, description, adapter toggles, model/category selects have `data-label`

**File:** `studio/src/renderer/src/components/Editor/ConfigForm.tsx`

**Expected:** `model` and `category` select/input elements have `data-label` attributes

**Actual:** The form renders `name` (`data-label="Config Name"`), `description` (`data-label="Config Description"`), and adapter toggles (`data-label="${adapter} Toggle"`). However `model` and `category` are listed in `KNOWN_KEYS` but are not rendered as interactive inputs — they fall through to the `unknownKeys` display as read-only `<span>` elements. No `data-label` is present for model or category.

---

## FAIL 5 — S-10: `__pathlyNavigate` does not support `'chat'`, `'files'`, or `'terminal'`

**Criterion:** Valid panel names are: `'monitor'`, `'chat'`, `'files'`, `'terminal'`

**File:** `studio/src/renderer/src/App.tsx` lines 181-187

**Expected:** `window.__pathlyNavigate('chat')`, `window.__pathlyNavigate('files')`, and `window.__pathlyNavigate('terminal')` navigate to the respective panels

**Actual:** The allowed set is `['plan', 'editor', 'flow', 'monitor', 'settings']`. Passing `'chat'`, `'files'`, or `'terminal'` throws `Error: Unknown panel: chat` (etc.), which is caught and returned as `{ success: false, error: 'Unknown panel: chat' }`.

- `'monitor'` works correctly (in allowed set, renders `<Monitor />`)
- `'chat'` is not routed — the chat panel is controlled by `uiStore.chatOpen`, not `setActivePanel`
- `'files'` is not a panel name in the app
- `'terminal'` is not a panel name in the app (terminal opens separately)

The criterion also states "Navigating to `'monitor'` switches the main panel to the Monitor view" — this part PASSES.
