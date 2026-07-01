# studio-home-redesign — User Stories

---

## S1 — Dark mode toggle on home page

**As a** returning user,
**I want** the dark/light mode toggle visible on the home screen,
**so that** I can switch themes without entering a project first.

**Acceptance criteria:**
- A sun/moon icon button appears in the top-right of the drag strip on the home screen
- Clicking it switches the theme (dark ↔ light) using the existing `setTheme` mechanism
- The icon reflects the current theme (Sun shown in dark mode, Moon shown in light mode)
- The button does not intercept window drag (uses `WebkitAppRegion: no-drag`)

---

## S2 — Grid layout with view toggle

**As a** power user with many projects,
**I want** projects displayed in a scrollable grid,
**so that** projects never disappear off screen regardless of how many I have.

**Acceptance criteria:**
- Projects render in a 3-column grid by default (2-col at medium width, 1-col narrow)
- Page scrolls vertically — no projects are clipped or hidden
- A grid/list toggle (LayoutGrid / List icons) appears in the section header row
- Grid is the default view; list view renders cards at full width in a single column
- View preference persists in `localStorage` under key `pathly-home-view`

---

## S3 — Welcoming headline

**As a** user opening the app,
**I want** a warm greeting below the Pathly Studio title,
**so that** the home page feels purposeful rather than bare.

**Acceptance criteria:**
- A subtitle line appears below "Pathly Studio" with text "Welcome back. Pick up where you left off."
- The subtitle uses `t.textMuted`, 14px, font-weight 400
- The subtitle animates with `fadeIn` (same as the h1)

---

## S4 — Richer project cards

**As a** user scanning the home page,
**I want** project cards to show more context at a glance,
**so that** I can identify the right project without opening it.

**Acceptance criteria:**
- Each card shows a 3px top accent border color-coded by activity state (blue = active, red = blocked, neutral = idle/done)
- Each card footer shows topic count ("N topics") and last-opened time
- The active feature name (first non-DONE, non-IDLE topic) appears with its flow badge and FSM badge
- The remove (×) button is only visible on card hover (opacity 0 by default, 1 on hover)
- Cards have a hover state: border color shifts toward accent with a subtle glow

---

## S5 — Pin/star favourite projects

**As a** power user with many projects,
**I want** to pin projects so they always appear at the top,
**so that** my most-used projects are immediately accessible.

**Acceptance criteria:**
- A star icon appears on card hover (or always visible when pinned)
- Clicking star toggles `pinned` on the `ProjectEntry` — persists via `updateProject`
- Pinned projects render above unpinned projects, separated by a labelled divider
- Unpinning a project moves it back to the recents section

---

## S6 — Improved empty state

**As a** new or first-time user,
**I want** a clear empty state on the home page,
**so that** I know exactly what to do when there are no projects.

**Acceptance criteria:**
- When `projects` is empty, show a centered `FolderOpen` icon (32px, muted), a title "No projects yet", and a subtitle "Open a folder to get started"
- The "Open project folder" CTA button is visible within the empty state area
