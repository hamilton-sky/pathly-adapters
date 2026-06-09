# Happy Flow — send-to-agent-diff

## Ideal user journey

1. User opens a skill markdown file in the Studio notebook (e.g. `reviewer.md`)
2. User selects text in the preview, adds two comments critiquing specific sections
3. User clicks "Send to Agent" in the comments panel footer
4. A terminal tab opens labeled "Review · reviewer.md" — Claude runs non-interactively
5. Claude reads the file and comments, rewrites to `reviewer.md.draft`, exits
6. Terminal tab shows agent summary; Studio detects draft existence
7. DraftDiffViewer overlay appears over the editor
8. Left panel shows 2 changed sections (with old/new text), 1 new section (added by Claude)
9. User reads both versions of section 1 — prefers the draft, leaves "Use draft" selected
10. User reads section 2 — prefers the original, clicks "Keep original"
11. User sees the new section — it looks good, checkbox stays checked
12. Right preview panel shows exactly what the file will look like
13. User clicks "Apply 2 changes"
14. Editor body updates immediately; diff viewer closes; `.draft` file is gone
15. User presses Ctrl+S — file saved cleanly

## What makes this flow feel right

- Zero file system risk: the original is untouched until the user explicitly confirms
- Section granularity: user doesn't have to accept or reject the entire rewrite
- Instant preview: no mental simulation needed — see the result before committing
- One click to discard: if Claude did something weird, "Reject draft" is right there
