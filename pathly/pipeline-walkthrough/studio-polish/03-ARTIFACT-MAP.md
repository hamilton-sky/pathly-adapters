# Artifact Map — studio-polish

**Date:** 2026-05-25

---

## Feedback File Archive

| File | Conv | Round | Resolved by |
|------|------|-------|-------------|
| ARCH_FEEDBACK_conv4_attempt1.md | 4 | 1 | architect (confirmed arch correct) + builder (moved main() to cli.py) |

Archived in: `pipeline-walkthrough/studio-polish/artifacts/`

---

## Source Files Changed

### New files (untracked → added)

| File | Conv | Purpose |
|------|------|---------|
| `src/install_cli/cli.py` | 4 | main(), _interactive_menu(), _uninstall_package() |
| `src/install_cli/orchestrate.py` | 4 | _run_host(), _run_host_uninstall(), ALLOWED_HOSTS, codegen helpers |
| `studio/src/renderer/src/components/FlowEditor/UnsavedChangesModal.module.css` | 2 | Navigation guard modal styles |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.test.ts` | 3 | 4 useFlowFile tests |
| `studio/src/renderer/src/components/FlowEditor/utils/validateFlow.test.ts` | 3 | 4 validateFlow tests |
| `studio/src/renderer/src/test-setup.ts` | 3 | Vitest global mocks (window.pathly) |
| `studio/vitest.config.ts` | 3 | Vitest config (jsdom, globals) |

### Modified files

| File | Conv | Change |
|------|------|--------|
| `studio/src/renderer/src/components/FlowEditor/index.tsx` | 1+2 | Skeleton loader (Conv 1); navigation guard + modal (Conv 2) |
| `studio/src/renderer/src/components/FlowEditor/hooks/useFlowFile.ts` | 1 | Wire up yamlParseError with line number from YAMLException |
| `studio/src/renderer/src/components/ui/Button.tsx` | 1 | loading prop + .loading CSS class |
| `studio/src/renderer/src/components/ui/Button.module.css` | 1 | Font fix (mono→base) + spinner animation |
| `studio/src/renderer/src/components/FlowWizard/WizardFooter.tsx` | 1 | Switch native button to Button component with loading={saving} |
| `src/install_cli/setup_command.py` | 4 | Reduced to 3-line thin shim |
| `studio/package.json` | 3 | Added vitest + @testing-library/react devDependencies |
| `tests/test_setup.py` | 4 | Patch targets updated: setup_command.* → cli.* |

---

## Plan Artifacts Written

| File | Stage |
|------|-------|
| `pathly/plans/studio-polish/DESIGN.md` | DESIGNING |
| `pathly/plans/studio-polish/STATE.json` | all stages |
| `pathly/plans/studio-polish/EVENTS.jsonl` | all stages |
| `pathly/plans/studio-polish/PROGRESS.md` | updated each conv |
| `pathly/plans/studio-polish/RETRO.md` | RETRO |
| `pathly/plans/studio-polish/ARCHITECTURE_PROPOSAL.md` | updated in RETRO (architect clarified) |
