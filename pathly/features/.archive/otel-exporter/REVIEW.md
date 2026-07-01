RESULT: PASS

Conv 2 — Batch CLI and CLI tests

Reviewer: PASS. One violation found and fixed during review cycle:
- Misleading `print("exported span: ...")` fired before dry-run guard; fixed so dry-run
  prints "dry-run: would export span: ..." and live path prints after successful export.
  Tests updated to assert correct stdout in both modes.

All 445 tests pass.
