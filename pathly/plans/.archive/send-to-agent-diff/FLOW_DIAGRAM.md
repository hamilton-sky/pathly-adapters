# Flow Diagram — send-to-agent-diff

```
User clicks "Send to Agent"
        │
        ▼
CommentsPanel.handleSendToAgent()
  buildSendPrompt(filePath, body, comments)
     └─ target: <filepath>.draft   ← Conv 1 change
        │
        ▼
window.pathly.terminal.spawn(tabId, cwd, argv)
  PTY: claude -p <prompt> --print --dangerously-skip-permissions
        │
        ├── registers terminal.onExit listener (tabId-scoped)
        │
        ▼
Claude writes <filepath>.draft (not original)
PTY exits
        │
        ▼
terminal.onExit fires → tabId matches
  fs.read(<filepath>.draft)
  ├── null?  ──→  onDraftReady never called (agent failed, no viewer)
  └── content? ──→ onDraftReady(<filepath>.draft)
        │
        ▼
Editor: setDraftPath(<filepath>.draft)
        │
        ▼
DraftDiffViewer mounts as overlay
  useDraftDiff(originalPath, draftPath)
  ├── fs.read(original) + fs.read(draft)
  ├── parseIntoSections (split on ## headings)
  └── compute DiffHunk[] (unchanged/changed/added/removed)
        │
        ▼
User reviews hunks (left panel)
  ├── changed: radio "Keep original" / "Use draft"
  ├── added:   checkbox include/exclude
  └── removed: checkbox keep/discard
Live preview updates (right panel)
        │
        ├── "Reject draft"
        │     ▼
        │   fs.delete(<filepath>.draft)
        │   setDraftPath(null)  →  original untouched
        │
        └── "Apply N changes"
              ▼
            reconstruct(hunks) → newContent
            fs.write(originalPath, newContent)  ← atomic via .tmp
            fs.delete(<filepath>.draft)
            setDraftPath(null)
            setBody / setConfig from newContent
            clearDirty(effectivePath)
              ▼
            Editor shows updated content
```
