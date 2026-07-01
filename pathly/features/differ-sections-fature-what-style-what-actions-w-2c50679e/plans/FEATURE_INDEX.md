# Feature Index — differ-sections (surface a)

Feature slug: `differ-sections-fature-what-style-what-actions-w-2c50679e`
Rigor: standard
Status: PLAN

## What this builds

Surface (a) of the Pathly board differ: a read-only **ArtifactDiffViewer** that shows
a structured hunk diff of an artifact file against the last committed git HEAD, plus an
**ImpactPanel** blade surfacing caller counts and affected flows per changed symbol.

The human supervisor opens this from an artifact card on the Command Center board.
They can see exactly what the agent changed, and — when the code graph is available —
how many callers each hunk touches, without leaving the board.

## What is NOT in scope

- Surface (b): hunk-level accept/reject write-back (next rollout phase)
- Surface (c): two-artifact compare
- Any new diff parsing library or code analysis engine
- Per-hunk comments or annotations
- Non-code artifact ImpactPanel (text diff only for markdown/JSON)

## Architecture summary

```
ArtifactDiffViewer (NEW — surface a container, read-only)
  useArtifactDiff (NEW — resolves git blob, feeds useDraftDiff)
    useDraftDiff (REUSED — extended with optional originalText param)
    window.pathly.git.blob (NEW IPC — git show HEAD:<relPath>)
  CodeDiffView (REUSED — extended with optional onHunkFocus + badgeFor props)
  ImpactPanel (NEW — blade: symbols / callers / flows)
    useImpact (NEW — POST /code/query op:"impact", normalize, cache)
      backend: detect_changes in CliProvider + code_context.py + query.py
```

Entry point: "See changes" button in ArtifactModal footer (MsgCard state: `showDiff`).

## Conversation table

| # | Name | Scope | Stories | Status |
|---|---|---|---|---|
| 1 | Git baseline IPC | git.ts + preload + global.d.ts + index.ts | US-1 | TODO |
| 2 | ArtifactDiffViewer + diff wiring | ArtifactDiffViewer + useArtifactDiff + useDraftDiff override + "See changes" button | US-2, US-3, US-4, US-5 | TODO |
| 3 | Badge + ImpactPanel frontend | CodeDiffView badge/focus props + ImpactPanel + useImpact (frontend only) | US-6, US-7, US-8, US-9 | TODO |
| 4 | Backend op:"impact" wiring | detect_changes in CliProvider + code_context.py passthrough + query.py branch | US-10, US-11 | TODO |
| 5 | Normalize + E2E verify | useImpact normalizer to real detect_changes shape + graceful degradation E2E | US-12, US-13 | TODO |

## Key files touched

| Layer | File | Change |
|---|---|---|
| Main IPC | `studio/src/main/ipc/git.ts` (NEW) | git:blob handler |
| Main wiring | `studio/src/main/index.ts` | registerGitHandlers() call |
| Preload | `studio/src/main/preload/index.ts` | expose pathly.git.blob |
| Types | `studio/src/renderer/src/types/global.d.ts` | git namespace |
| Renderer | `DraftDiffViewer/ArtifactDiffViewer/` (NEW) | container + hook + CSS |
| Renderer | `DraftDiffViewer/ImpactPanel/` (NEW) | blade + CSS + ImpactRow |
| Renderer | `DraftDiffViewer/useImpact.ts` (NEW) | /code/query fetch + cache |
| Renderer | `CodeDiffView/CodeDiffView.tsx` | +onHunkFocus +badgeFor props |
| Renderer | `MsgCard.tsx` / `ArtifactModal.tsx` | "See changes" button + showDiff state |
| Backend | `runner/code_context_cli.py` | +detect_changes method |
| Backend | `runner/code_context.py` | +detect_changes passthrough |
| Backend | `http_server/blueprints/code/query.py` | impact op branch |
