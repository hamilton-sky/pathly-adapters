# Studio-bridge Run 1 — SPEC

## Goal
Silence the noisy sentence-transformers / HuggingFace weight-load logs emitted on headless
embedding init, while proving the Studio -> PTY -> claude bridge and that the loop agent writes
an AGENT_DONE with an explicit `outcome`.

## Task 1 — Silence embedding model-load logs
In `src/pathly_orchestrator/runner/embeddings.py` (`_load_model`), quiet the transformers
"Loading weights" progress bar and "BertModel LOAD REPORT" before constructing
`SentenceTransformer('all-MiniLM-L6-v2')`: set `transformers.utils.logging.set_verbosity_error()`
and `os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'` (before the sentence_transformers import).
Keep the existing try/except fallback to `_model = None`. Do NOT change embedding behavior.

## Task 2 — Verify
Run `PYTHONPATH=src python -c "import pathly_orchestrator.runner.embeddings as e; e._load_model()"`
and confirm the progress bar and LOAD REPORT no longer print to stderr. Report before/after in the
completion summary; if noise persists, report `outcome=failed`.

## Acceptance criteria
- No "Loading weights" progress bar or "BertModel LOAD REPORT" on headless `get_db()` init.
- Embedding output is unchanged (same vectors).
- Graceful degradation preserved: a missing `transformers` / `sentence_transformers` dep still
  falls back to `_model = None`.

## Out of scope
- Do not touch embedding storage, search, or the DB schema; do not add new dependencies.
