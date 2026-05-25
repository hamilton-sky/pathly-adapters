# PO Notes — studio-home-redesign

_Last updated: 2026-05-20_

## Who Is This For
Returning power-user developers who open Pathly Studio daily. The home page is a fast re-entry hub, not an onboarding screen. Users know what Pathly is; they just need to get back to work quickly.

## Definition of Success
User opens the app and is inside a project within ≤2 clicks, with no overflow/disappearing-card bug. Grid layout with scroll handles any number of projects. Secondary success: the page feels warm and professional, not bare.

## Requirements
- **Grid layout** as default view (2–3 columns), with scroll so projects never disappear
- **List view toggle** — grid/list switcher in the header
- **Dark mode toggle** visible in the home page header (already exists in-app, just missing here)
- **Richer project cards** — show: last active timestamp, topic count, active feature name/status badge, project path
- **Pin/star projects** — allow favouriting so pinned projects always appear first
- **Welcoming headline** — short warm tagline above the project grid (not a full onboarding wizard)
- **"Open project folder" CTA** stays prominently placed
- **Show all / search** handles discovery of older projects; home page shows last 8–12

## Out of Scope
- Project CRUD (create/rename/delete) from home page
- New-user onboarding wizard
- Analytics or stats panels
- Notifications center

## Constraints
- Electron desktop app (React frontend)
- Must match existing Studio design language and component patterns
- Dark mode toggle already implemented in-app — reuse existing mechanism
- No new external dependencies without discussion

## Open Questions
- Should pinned projects have a separate visual section, or just float to the top of the grid?
- What's the max number of projects shown before "Show all" kicks in — 8 or 12?
- Should cards show a project color/avatar for quick visual scanning?
