# Review Failures — Conv 3

## [IMPL] 1 — BlockAuthorForm/index.tsx — Wrong filename
studio/CLAUDE.md mandates `ComponentName/ComponentName.tsx`. File must be `BlockAuthorForm/BlockAuthorForm.tsx`, not `BlockAuthorForm/index.tsx`.

## [IMPL] 2 — BlockAuthorForm — Component not integrated; user-blocks.json write missing
Phase 6 spec: "Write/merge result into ${pathlyUserHome}/user-blocks.json". The component delegates to onSave but no parent calls writeFile. Component is never imported anywhere — dead code.
Fix: Component should write user-blocks.json directly. Add a "New block" button + BlockAuthorForm toggle in Step4Agents so the form is reachable and triggers the write.

## [IMPL] 3 — Step4Agents/Step4Agents.tsx:31 — Direct window.pathly.fs.read instead of readFile wrapper
All wizard-layer files use `import { readFile } from '../../services/pathlyApi'`. Step4Agents calls `window.pathly.fs.read()` directly — inconsistent with the layer pattern.
Fix: import `readFile` from `../../../services/pathlyApi` and use it.

## [IMPL] 4 — Step4Agents/Step4Agents.tsx:37,40 — Wrong console.warn prefix
Messages say "BlockAuthorForm:" but the code is in Step4Agents.tsx.
Fix: change to "Step4Agents:".

## Warning (non-blocking, fix anyway)
FlowWizard.tsx `startBlank` function resets all state fields but does not call `setBlockMap({})`. Stale blockMap values survive a "start blank" action.
