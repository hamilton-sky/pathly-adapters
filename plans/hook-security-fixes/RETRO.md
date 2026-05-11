# Retro — hook-security-fixes

## What went well

- Both conversations completed with all 6 stories delivered and `pytest -q` green.
- Clear two-phase split (Python fixes in Conv 1, README docs in Conv 2) prevented scope creep.
- PO consult surfaced 6 real gaps before any build started — every gap found a clean fix in the plan.
- Atomic rollback and manifest guard were already present in `materialize.py`; builder verified rather than re-implemented.
- Tests stayed fast and isolated: no network, no real API keys, `tmp_path` throughout.

## What was surprising / harder than expected

- **Hook scripts did not exist anywhere in the repo.** A full-repo search across `.py`, `.yaml`, `.json`, `.toml` found nothing. Case C (create stubs + register in install.yaml) was the outcome — a hidden dependency not evident from the stories.
- **`plans_dir.resolve()` caught by reviewer.** Both hook files constructed `plans_dir` without resolving it, making `is_relative_to()` unreliable on symlinked project roots. A subtle but critical security defect.
- **Weak test assertion (`or True`).** The MCP config invalid-JSON test had `or True` making it always pass. And the no-traceback assertion used a vacuous disjunction. Both passed initial test runs but were caught in review.
- **Python version claim was wrong.** Story 6 originally said `Path.resolve()` requires Python 3.11+ — incorrect. Correct claim: `Path.is_relative_to()` requires 3.9+. Would have shipped a factually wrong README without the PO consult.

## What to do differently next time

- **Treat hook/script existence as a Phase 0 blocker.** Before writing any hook-related stories, search the repo. Build Case C costs into the plan when scripts are absent.
- **Review guard code both sides.** When adding `is_relative_to()` guards, both sides (the input path AND the reference path) must be resolved. Make this a named checklist item in security-focused conversation prompts.
- **Validate test assertions adversarially.** For security tests, write a "should fail if the guard is removed" note alongside each assertion. This catches vacuous assertions before review.

## Candidate lessons

1. **For hook/script features, search before writing.** Enumerate the three cases (found as `.py` / found embedded / not found) and document the Case C action (create + register) in the conversation prompt before spawning the builder.

2. **Two-sided resolution rule for path guards.** Whenever `Path.is_relative_to()` is used as a security boundary, both the tested path and the reference path must be resolved with `.resolve()`. Add this as a named checklist item in any security-hardening conversation prompt.
