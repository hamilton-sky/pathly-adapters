# Board Evaluation

## Classification
BOTH

## Summary
The board is centered on the `lsp-integration` smoke-test phase, but the surrounding artifacts
show unresolved gaps across the whole code-intel stack: `lsp-integration` depends on
`gitnexus-integration` rails, the initiative sequencing says A should follow B-core and C, and
the live task text asks for proof that Serena works, falls back cleanly, and does not impose
unacceptable startup cost. This is BOTH because there is concrete implementation and verification
work to run now (`uv`, `pathly-setup`, MCP propagation, live explorer traces) and a research
surface that is still undecided (`--project-from-cwd` correctness in runner mode, startup
latency, and what exact fallback contract applies when Serena or GitNexus is missing or stale).
There is also a documentation inconsistency: the task text says "all 4 APPROACH.md open
questions" but `lsp-integration/APPROACH.md` explicitly lists three, so the acceptance target is
currently ambiguous.

## Key unknown / risk
Whether Serena is reliable enough to recommend beyond interactive symbol-precision use, given
runner-mode root resolution, `uv` and language-server availability, and startup latency on short
headless runs.

## Recommended next steps
- Verify the Serena release contract in the real environment: `uv` on PATH, launch command
  validity, and the four documented read-only tool names.
- Confirm dependency readiness before the smoke test: whether the GitNexus `_run_mcp` rails and
  prompt-section changes are already shipped, or whether this phase must exercise the
  dependency-fallback path described in `APPROACH.md`.
- Run `pathly-setup claude --apply`, then verify the installed host config and generated prompts
  contain the expected Serena and GitNexus surfaces.
- Run a live explorer trace on a precise symbol question and confirm the evidence explicitly
  cites `find_referencing_symbols`, not just equivalent Grep output.
- Run a Serena-absent control trace and document the exact fallback path taken: GitNexus,
  native Grep/Read, or failure, including what conditions triggered that path.
- Measure first-run and repeat-run Serena startup latency, then record whether headless short
  runs should prefer GitNexus while interactive sessions use Serena for exact symbol work.
- Reconcile the acceptance criteria mismatch around "4 open questions" versus the three listed
  questions in `APPROACH.md`, so the phase has an unambiguous completion target.
