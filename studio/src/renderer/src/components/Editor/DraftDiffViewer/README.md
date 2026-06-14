# DraftDiffViewer

Section-level review modal for agent-generated markdown drafts, in the Pathly
Studio visual language. A builder agent stages a draft; this modal lets the user
accept or reject each changed section before the result is written to disk. Four
layouts, toggled in the header and remembered across sessions: Cards (master-detail),
List (compact triage), Code (VS Code-style split/unified file diff), and Edit
(hand-tweak the reconstructed result before applying). Word-level diff is the default.

Built as small, single-responsibility components — every component in its own
folder with a sibling CSS module (no inline styles), against the project tokens.

## Structure

Root utilities + hooks:
- index.ts — barrel, public exports
- useDraftDiff.ts — load + diff + per-hunk accept/review state + setAll (window.pathly.fs)
- useViewMode.ts — view-mode state ('cards' | 'list' | 'code' | 'edit'), persisted to localStorage
- diffUtils.ts — computeWordDiff (prose), computeLineDiff (code), countWordChanges
- hunkLabels.ts — statusBadgeLabel / acceptChipLabel / displayHeading / previewText

Reusable atoms (shared by cards + triage rows):
- StatusBadge/ — ADDED / REMOVED / CHANGED pill
- AcceptToggleChip/ — the accept/reject pill
- ViewToggle/ — icon-only Cards | List | Code | Edit segmented control
- icons/Icons.tsx — inline lucide-style CardsIcon / ListIcon / CodeDiffIcon / EditIcon / Chevron
- DiffCodeBlock/ — word-level inline diff (default) or line diff (mode line)
- MarkdownRenderer/ — minimal markdown for the Result tab

Composed components:
- DraftHunkCard/ — one notebook-cell hunk (Cards view); expands to its diff
- DraftHunkList/ — the Cards-view left panel (CHANGES list + count)
- DraftTriageRow/ — one dense triage row; click opens its diff inline
- DraftTriageList/ — the List view (rows + Accept all / Reject all)
- DraftPreviewPanel/ — Cards-view right panel (Result / Changes / Diff tabs)
- CodeDiffView/ — read-only file-level diff with Split ⇄ Unified sub-toggle
- DraftEditView/ — editable result pane (MarkdownEditor seeded from reconstruct())
- DraftDiffFooter/ — discard / close / apply + unreviewed warning + confirm
- DraftDiffViewer/ — parent modal: header + ViewToggle, switches Cards / List / Code / Edit

## Props (DraftDiffViewer)

- originalPath: path to the original markdown
- draftPath: path to the staged draft
- onApply(newContent): called with the reconstructed result
- onClose(): dismiss the modal
- onDiscard(): permanently delete the draft (after in-modal confirm)
- pushToast(message, kind): optional toast hook for the no-changes notice

View mode is internal (useViewMode) and persisted; no prop needed. Lift it to a
prop if a host wants to control it.

## Behaviour notes

- Cards view: master-detail. Cards expand inline to a word diff; right panel has
  Result / Changes / Diff tabs.
- List view: single-open accordion — opening a row collapses the previous one, so
  the list stays short at high change counts. Bulk Accept all / Reject all.
- Edit view: the reconstructed result in a CodeMirror editor, seeded from the
  current accept/reject choices. Once the user types, the manual buffer overrides
  the toggles and wins on Apply ("Apply edited result"); "Reset to reconstructed"
  drops the edit and follows the toggles again. Editing is the escape hatch for
  changes no per-section toggle can express.
- Icon-only toggle; choice persisted in localStorage (pathly.diffViewMode).
- Word-level diff highlights changed words (red strikethrough = removed, green =
  added). DiffCodeBlock mode line gives the classic line diff for code.

## External integration points

- window.pathly.fs.read (useDraftDiff.ts): Electron preload bridge, global in Studio
- MarkdownRenderer: local minimal renderer; swap for your shared one in-app
- icons/Icons.tsx: inline SVGs; swap for lucide-react in-app if preferred
- pushToast (prop): optional; decoupled from the toast store

All styling resolves from the global Pathly tokens (tokens.css), so the modal
re-themes automatically with any data-theme palette.
