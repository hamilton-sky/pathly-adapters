# help

This is the canonical, tool-agnostic Pathly behavior for the help workflow.
Adapter skills should load and follow this prompt instead of duplicating workflow logic.

## Adapter Surface

This core prompt names Pathly workflows and menu actions. Adapters translate
those actions into their native surface. Do not hardcode menu prose here.
Render the menu payload returned by the FSM-backed Python surface or active
state endpoint instead.

## Doctor mode (`doctor`)

If `$ARGUMENTS` contains `--doctor`, run the diagnostic flow for the target
feature. Keep the diagnostics read-only and report the result in plain language.

## Step 1: Detect state

Detect the active feature and infer the current workflow state from `pathly/features/`.
If there is no active feature, treat help as a start-of-workflow entry point.

## Step 2: Render menu payload

If the backend returns a `menu` payload, render it directly. If there is no
payload, fall back to a minimal prompt that asks the user what they want to do.
Do not embed static state-by-state menu prose in this file.

## Step 3: Full command reference

When the user explicitly asks for the full command reference, show the command
surface summary from the canonical Pathly command docs or the current backend
surface. Keep the menu content centralized in Python.
