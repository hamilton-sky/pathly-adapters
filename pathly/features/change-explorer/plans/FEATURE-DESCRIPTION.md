# Change Explorer Feature Description

## What this feature is

`change-explorer` is a Pathly Studio panel for reviewing project changes without leaving the app.

It is the first phase of a broader "Diff section" direction. The immediate goal is a live, read-only git diff viewer inside Studio.

## Problem it solves

Today, when an agent or pipeline changes files, the user has to leave Pathly Studio and open a terminal or VS Code to inspect the diff.

That breaks focus and makes review slower.

## Core user value

With Change Explorer, the user can:

- See all uncommitted project changes in one Studio panel
- Select any changed file and inspect its diff
- Switch between split and unified diff views
- Refresh manually
- See live updates while a pipeline run is active

## Planned behavior

### Phase 1

- Show all working-tree changes from git
- Display file status and added/removed line counts
- Open a file diff in the right-hand pane
- Reuse the existing diff viewer primitives from `DraftDiffViewer`
- Add a Studio sidebar entry and keyboard shortcut

### Phase 2

- Poll automatically while runs are active
- Show a `LIVE` badge when polling is on
- Stop polling when the run is idle, done, aborted, or errored

## Expected UI shape

- Left pane: changed file list
- Right pane: selected file diff
- Header: title, file count, live badge, refresh action

## Technical direction

- Main process runs git diff commands
- Renderer reads results through a new `git:diff` IPC channel
- Studio reuses shared split/unified diff rendering pieces
- Runner status controls whether polling is active

## Relationship to the larger diff vision

`SPEC.md` defines the first deliverable: a read-only, git-backed change viewer.

`DIFF-SECTION-SPEC.md` describes the broader follow-up vision:

- a full diff section for code and markdown
- support for agent proposals, not only git working-tree changes
- future accept/reject or staging flows for code hunks

So the feature can be summarized as:

> A live Studio panel that lets users inspect all project changes in one place, starting with git diffs and later expanding into a full review surface for agent-generated changes.

## Current status in this folder

- `SPEC.md`: concrete Phase 1 Change Explorer spec
- `DIFF-SECTION-SPEC.md`: umbrella architecture for the larger diff system
- No implementation state file is present in this folder right now
