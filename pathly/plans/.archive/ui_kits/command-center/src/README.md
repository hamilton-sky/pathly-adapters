# Command Center — TypeScript components

A small, well-factored TypeScript + React componentization of the Command Center
(comms board) layout — extracted from the kit's vanilla `command-center.js` and
structured per **`comms-board/UI-DIRECTION.md §7`**. This is the developer-handoff
source for building the feature in Studio.

> The kit's `index.html` + `command-center.js` remain the **canonical visual spec**
> (vanilla JS, for pixel-perfect offline rendering in the Design System tab). This
> `src/` folder is the same layout expressed as typed components you can drop into
> Studio's Vite/React build.

## Structure

```
src/
  types.ts                 Domain + UI types (Message, Feature, BoardScope, …)
  agents.ts                Agent identity, stage colours, SCOPES, compose types
  seed.ts                  Demo features + boards (replace with FSM data in Studio)
  Icon.tsx                 lucide wrapper over window.PathlyIcons (→ lucide-react)

  store/
  useCommsStore.tsx        Source of truth: features + boards + post/answer/resolve
  useCommandCenter.ts      Workspace UI state: sections, preset, direction, sidebar
  useCommsPanel.ts         Per-section binding: messages + handlers + flash
  useSectionResize.ts      Drag-to-resize between sections

  CommsPanel (thread building block)
  CommsPanel.tsx           Thread shell: list + read-scope toggles + compose bar
  CommsMsgList.tsx         Pinned-decisions tray + message thread
  CommsMsgCard.tsx         Per-type card (notebook-cell style + type badge chip)
  CommsInput.tsx           Compose bar + message-type picker (⌘/Ctrl+Enter sends)
  MessageTypeBadge.tsx     Tinted mono type chip
  Avatar.tsx               Agent / "you" avatar

  CommandCenter (workspace)
  CommandCenter.tsx        Workspace shell: header + sidebar + board sections
  CommandCenterHeader.tsx  Section tabs, presets menu, direction toggle, exit
  FeatureSidebar.tsx       Left nav: feature cards (accordion) / collapsed rail
  FeatureCard.tsx          One feature card + "Set as main ↗" + status actions
  BoardSection.tsx         Full-area section hosting one CommsPanel

  index.tsx                Entry — <CommsProvider><CommandCenter/></CommsProvider>
  command-center.css       Shared styles (className strings; → CSS Modules in Studio)
```

## Conventions / wiring notes

- **No npm deps beyond React.** The store is plain React context so it runs anywhere;
  swap it for `zustand` (`store/commsStore.ts`, the Studio `chatStore.ts` pattern)
  without touching consumers.
- **Styling** is via the design-system tokens + the class names in `command-center.css`.
  In Studio, split these into co-located `*.module.css` per the spec.
- **Icons** come from `window.PathlyIcons` (the self-hosted lucide subset). In Studio,
  replace `Icon` with `lucide-react`.
- **Data** is seeded from `seed.ts`. In Studio, hydrate `useCommsStore` from
  `GET /comms` and subscribe `useCommsPanel` to `GET /events/comms` (SSE) — see
  `comms-board/SPEC.md §10`.
- **No emoji** in product UI: message type is carried by the left-of-frame type
  badge chip + colour, matching the Skill Notebook cell language.
```
```
