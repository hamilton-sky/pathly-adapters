# DESIGN.md — studio-home-redesign

_Last updated: 2026-05-20_

---

## Sources Used

- **PO Notes**: `PO_NOTES.md` in this folder
- **UI/UX Pro Max design-system**: developer tool / productivity hub
- **Web research**: Figma, JetBrains, VS Code, Linear, Atarim, Eleken, Mockplus patterns

---

## Design System

| Token | Value | Notes |
|---|---|---|
| **Style** | Clean minimal + developer-first | Match existing Studio aesthetic |
| **Font (heading)** | Inter 700 | Existing `t.fontFamilyBase` |
| **Font (body/label)** | Inter 400/500 | Existing `t.fontFamilyBase` |
| **Font (paths)** | Monospace | Existing `t.fontFamilyMono` |
| **Accent** | `t.accent` (#2563EB range) | Existing blue |
| **Success** | `t.green` | Topic active / live states |
| **Danger** | `t.red` | Blocked states |
| **Surface** | `t.bgMantle` | Card background |
| **Border** | `t.bgSurface0` | Card borders |
| **Animation** | `fadeSlideUp` 300ms ease-out | Already defined in component |

---

## Layout — Full Page Structure

```
┌──────────────────────────────────────────────────┐
│  Drag strip (36px, t.bgMantle)          [☀/🌙] [≡]│  ← header controls in drag strip
├──────────────────────────────────────────────────┤
│                                                  │
│       Pathly Studio                              │
│       Welcome back — pick up where you left off  │  ← warm subtitle
│                                                  │
├─────────────────────────────────────────────────-┤
│  RECENT PROJECTS          [👁 Show all] [⊞][≡]   │  ← section header with view toggle
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Card     │  │ Card     │  │ Card     │       │  ← 3-col grid (default)
│  └──────────┘  └──────────┘  └──────────┘       │
│  ┌──────────┐  ┌──────────┐  ...                 │
│  │ Card     │  │ Card     │                      │
│  └──────────┘  └──────────┘                      │
│                                                  │
├──────────────────────────────────────────────────┤
│            + Open project folder                 │  ← CTA, centered, accent outline
└──────────────────────────────────────────────────┘
```

- **Max content width**: 1100px (was 820px — widen to accommodate 3-col grid)
- **Grid columns**: 3 at ≥900px, 2 at 600–900px, 1 below 600px
- **Grid gap**: 14px
- **Scroll**: full page scroll (`overflow-y: auto` on the root div — currently `minHeight: 100vh` which is correct, but container must NOT clip children)
- **Pinned section**: if any project is pinned, render a "Pinned" label + pinned cards first, then a divider, then "Recent" label + rest

---

## Header Controls (Drag Strip)

The drag strip is the only "header" on the home screen. Add controls to the **right edge**, offset from the draggable zone using `pointer-events: all` and `WebkitAppRegion: no-drag`.

```
[ drag zone ................ ]  [☀/🌙 toggle]  [⊞ grid | ≡ list toggle]
```

- **Dark mode toggle**: reuse the exact same `setTheme` pattern from `TopBar.tsx:142` — `setTheme(theme === 'dark' ? 'light' : 'dark')` with `Sun`/`Moon` icons from lucide-react
- **View toggle**: two icon buttons side by side — `LayoutGrid` and `List` from lucide-react. Active state: `color: t.accent`, inactive: `color: t.textMuted`
- Both controls: `width: 28px`, `height: 28px`, `border-radius: 6px`, hover `background: t.bgSurface0`
- Store view preference in `localStorage` key `pathly-home-view` (`'grid' | 'list'`), defaulting to `'grid'`

---

## Welcome Headline

Replace the bare `<h1>Pathly Studio</h1>` with a two-line header:

```
Pathly Studio          ← h1, existing style
Welcome back.          ← subtitle, 14px, t.textMuted, font-weight 400
Pick up where you left off.   ← or a single tagline depending on preference
```

- Keep it short — this is a **power-user home**, not an onboarding screen
- Animation: `fadeIn 400ms ease-out both` (same as existing h1)
- Margin below: reduce from `36px` to `24px` since the subtitle adds visual weight

---

## Project Card — Grid View

Each card is a `div` with:

```
┌─────────────────────────────────────────────────┐
│ ░░░░ [accent color strip, 3px top border-radius] │  ← top color accent
├─────────────────────────────────────────────────┤
│ 🔖  project-name                     ★ pin  ×  │  ← name + star + close
│     C:\Users\...\path                            │  ← mono path, truncated
├─────────────────────────────────────────────────┤
│  active-feature-name        [team] [Storming]   │  ← top topic + badges
│  + 2 more topics                                │  ← count of additional topics
├─────────────────────────────────────────────────┤
│  3 topics  ·  2 hr ago              → Open      │  ← footer meta + CTA
└─────────────────────────────────────────────────┘
```

### Card spec

| Property | Value |
|---|---|
| Background | `t.bgMantle` |
| Border | `1px solid t.bgSurface0` |
| Top accent border | `3px solid` — use `t.accent` for active projects, `t.bgSurface1` for idle |
| Border radius | `10px` |
| Padding | `14px 16px` |
| Min height | `none` — let content drive height |
| Hover | border color → `t.accent + '50'`, box-shadow `0 0 0 1px t.accent + '30'` |
| Transition | `all 150ms ease-out` |
| Pin indicator | `★` icon (lucide `Star` / `StarOff`), 14px, top-right area; filled gold when pinned |
| Active feature row | show only the **first active non-DONE topic** name + FlowTypeBadge + FsmBadge |
| Topic count | `"N topics"` where N = total plans count (all states) |
| Path | mono 10px, `text-overflow: ellipsis`, `max-width: 160px` |
| Open button | `→ Open` — right-aligned in footer row, existing style |
| Remove button | `×` — top-right corner, 24×24px, shows on card hover only (opacity 0 → 1) |

### Color accent logic for top strip

```
active (non-DONE, non-IDLE state) → t.accent  (blue)
blocked                           → t.red
done / all-idle                   → t.bgSurface1 (neutral)
pinned + active                   → t.accent
```

---

## Project Card — List View

Identical to the existing card design, but:
- Full width (single column)
- No top accent strip — instead a left `3px` border with the same color logic
- Topic rows remain inside the card as-is (existing design is already good for list)
- Add topic count and pin/star to the header row

---

## Empty State

When `sorted.length === 0`:

```
┌────────────────────────────────────────────────┐
│                                                │
│     (folder icon, 32px, t.textMuted)           │
│     No projects yet                            │
│     Open a folder to get started              │
│                                                │
│         + Open project folder   ←  CTA inline │
└────────────────────────────────────────────────┘
```

- Center aligned, `padding: 48px 32px`
- Icon: lucide `FolderOpen`, 32px, `t.textMuted`
- Title: 14px, `t.textPrimary`, weight 500
- Subtitle: 12px, `t.textMuted`

---

## "Show all / Hide done" Control

Keep existing `Show all / Hide done` toggle but move it to the section header row alongside the view toggle:

```
RECENT PROJECTS    [Show all]   [⊞ ≡]
```

- Same existing button style

---

## Pinning Behaviour

- Add `pinned?: boolean` to `ProjectEntry` type in `types.ts`
- `updateProject(path, { pinned: true })` persists to store (already uses localStorage)
- On `sorted` array: partition into `pinned` (sorted by `lastOpened`) and `unpinned` (sorted by `lastOpened`), render pinned first
- Visual separator between pinned and recent sections: a `1px solid t.bgSurface0` divider with the labels "Pinned" / "Recent" in the same muted uppercase style as "Recent Projects" today

---

## Animations

Preserve all existing animations. Add:
- Cards entering grid: stagger `55ms` per card (already implemented) — keep
- Star toggle: `scale(1.2)` flash on click, `150ms ease-out`
- View toggle switch: cards fade out (`opacity: 0, transform: scale(0.97)`) then fade in new layout — `150ms`

---

## Accessibility

- All interactive elements: `cursor: pointer`
- Star button: `aria-label="Pin project"` / `"Unpin project"`
- View toggle buttons: `aria-label="Grid view"` / `"List view"`, `aria-pressed` state
- Dark mode toggle: `aria-label="Switch to dark mode"` / `"Switch to light mode"`
- Remove button: `aria-label="Remove {project.name} from list"`
- Focus rings: preserve existing `outline` behavior — do not add `outline: none` anywhere

---

## Files to Change

| File | Change |
|---|---|
| `HomeScreen.tsx` | Main redesign — grid, header controls, richer cards, pinning |
| `store/projectStore.ts` (or wherever `ProjectEntry` lives) | Add `pinned?: boolean` field |
| `types.ts` | Add `pinned?: boolean` to `ProjectEntry` |

No new dependencies needed — `lucide-react` already available (`Sun`, `Moon`, `LayoutGrid`, `List`, `Star`, `FolderOpen` icons).

---

## What NOT to Change

- `FlowTypeBadge` and `FsmBadge` components — keep as-is, they're correct
- `timeAgo` helper — keep
- Animation keyframes — keep
- `handleOpen`, `handleOpenFolder` logic — keep
- Store API (`addProject`, `removeProject`, `updateProject`) — keep, only add `pinned` field
- `scanRoot` / `loadAllPlans` logic — keep entirely
