# Security Hardening Feature Retrospective

## What Went Well
- **Systematic ownership model**: ptyOwners tabId tracking cleanly isolated terminal operations (write/resize/kill/popout) with minimal surface area.
- **Test-driven validation**: test_storage.py rotation tests, manifest hash mismatch, and rollback stderr capture added coverage for logic that was correct but untested.
- **Clean dependency removal**: Dead HTTP telemetry server.py/__main__.py removal simplified the codebase with no side effects.
- **Build config hygiene**: .gitignore addition for build/lib/ prevented accidental binary commits.

## What Was Surprising
- **Ownership checks incomplete in initial build**: Reviewer caught 3 missing validations on resize/kill/popout that initial implementation overlooked — the plan specified write and spawn, but did not explicitly call out the other handlers.
- **app.getAppPath fallback risk**: The `cwd || app.getAppPath()` fallback silently bypassed the intent of isValidCwd — a subtle case that wouldn't fail any test but violated the trust boundary contract.

## Lessons for Future Features
- **List every IPC handler explicitly in the plan phase** when adding ownership checks — don't assume "all handlers" is obvious to the builder.
- **No-fallback is the right default for security paths** — explicit error > silent default.
- **Storage hygiene and security changes bundle well** — log rotation and dead code removal added no risk and cleaned up the module in one pass.
