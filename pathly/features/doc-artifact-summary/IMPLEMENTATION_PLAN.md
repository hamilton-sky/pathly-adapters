# Implementation Plan — Doc Artifact Summary

Each phase maps to one board task. Layering: `db/ → (none)`, `runner/ → db`, `http_server/ → all`
(supervisor/runner imports **lazy, inside handlers**). Hard limit 400 lines/file. Renderer: CSS
modules + `tokens.css` only, ~150 lines/component, one component per folder.

The whole feature rests on **one idempotent core** + **one resolver mirrored TS/Py**:

```
ensure_converted(path) -> md_path | None      # runner/artifact_convert.py (idempotent, atomic, never raises)
resolve_text_source(path[, atype]) -> path    # runner/artifact_text.py  +  resolveTextSource.ts (pure mirror)
```

`resolve_text_source`: for a convertible extension whose `<path>.md` sidecar exists → return the
sidecar; for a text file → return itself; else → return the original (gates then reject it as
before). Inserted **in front of** each existing gate — predicates unchanged.

---

## Phase 1 — Summaries on drop (MVP)

**Goal:** drop `.pdf`/`.docx`/`.pptx` → card + summary, identical to `.md`, for every target.

### New files
- `src/pathly_orchestrator/runner/artifact_text.py` — pure: `CONVERTIBLE_EXTS`, `ext_of`,
  `is_convertible`, `converted_sidecar(path) -> f"{path}.md"`, `is_text`,
  `resolve_text_source(path, atype=None)`. Imports stdlib only (`os.path.exists`).
- `src/pathly_orchestrator/runner/artifact_convert.py` — `ensure_converted(path) -> str | None`:
  idempotent (skip if `<path>.md` newer than source), **lazy** `from markitdown import MarkItDown`
  inside the fn, size cap, empty-output guard (do **not** write empty `.md`), **atomic** write
  (`<path>.md.tmp` → rename), never raises → returns `None` on any failure. Also
  `convert_artifact_async(...)` (Phase-2 daemon; mirrors `index_artifact_async`).
- `src/pathly_orchestrator/http_server/blueprints/comms/artifacts_convert.py` —
  `POST /comms/artifacts/convert` (lazy-imports `runner.artifact_convert`). Mirrors the existing
  `artifacts_summary.py` split. Register in `http_server/app.py` `all_blueprints`.
- `studio/src/renderer/src/services/resolveTextSource.ts` — pure TS mirror + async
  `resolveTextSource(path, atype): Promise<string | null>` (calls `apiConvertArtifact` for
  convertibles, returns the sidecar; returns original for text; `null` on convert failure).

### Changed files
- `studio/src/renderer/src/store/commsApi.ts` (~`:281`, after `apiPostArtifact`) — add
  `apiConvertArtifact(path, atype?) -> { ok, md_path, reason? }`.
- `summarizeArtifact.ts:28` — widen gate: `isTextExt(name) || isConvertible(name)`.
- `summarizeArtifact.ts:97-99` — insert `const src = await resolveTextSource(abs, atype); if (!src) return false;` then `readFile(src)`; `:118` engine out becomes `${src}.summary`.
  (`handleSummaryRequest → summarizeArtifactById` inherits this — covers the SSE path too.)
- `pyproject.toml:10` — add `markitdown[pdf,docx,pptx]` to `dependencies` (bundle, D3). Verify the
  existing `pdfplumber` pin satisfies `>=0.11.9` (markitdown's `pdf` extra floor).

### Untouched (verified safe)
`ArtifactsView.tsx:57` and the `CommsPanel.tsx:151` drop loop (still `void summarizePosted`); the
`minilm` post; the `atype` fork (conversion keys off extension).

### Failure contract (`POST /comms/artifacts/convert`)
```
req : { path: "<abs>", atype?: "pdf|docx|pptx", artifact_id?: "<id>" }
200 : { ok:true,  converted:true,  md_path:"<path>.md", chars:N, cached:false }
200 : { ok:true,  converted:false, md_path:"<path>" }        # already text / not convertible
200 : { ok:false, reason:"converter_missing|conversion_failed|empty_output|too_large|not_found", md_path:null }
400 : { error:"path required / not absolute" }               # malformed input only
Idempotency: <path>.md newer than <path> ⇒ return cached. Atomic: .tmp then rename.
```

### Tests
- `tests/…/test_artifact_convert.py`: fixture `.pdf`/`.docx`/`.pptx` → non-empty markdown; empty
  fixture → `None`, no sidecar written; missing markitdown (monkeypatch import) → `None`
  (`converter_missing`). Idempotency + atomic-rename.
- `tests/…/test_artifact_text.py`: `resolve_text_source` matrix (convertible+sidecar, convertible
  no-sidecar, text, other).
- Renderer: extend `summarizeArtifact.test.ts` — a pdf artifact resolves to `report.pdf.md` and
  summarizes; missing sidecar → best-effort skip (no throw).
- Rerun `scripts/gen_test_index.py`.

### Phase-1 DoD
US-1..US-5 pass. Drop a PDF/Word/PPT → card instantly → summary appears like `.md`. Scanned/empty →
card + explicit "no text" state. `npm run typecheck` + `tsc -p tsconfig.node.json` + `pytest` green.

---

## Phase 2 — Context catalog + index + embeddings (core for this feature)

**Goal:** converted docs are section-hydratable into agent prompts and semantically searchable
(US-6). Same `ensure_converted` core, triggered server-side at post + resolver at the read gates.

### Changed files
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_write.py` (~`:296-321`, beside the
  existing `index_artifact_async`) — for convertible artifacts, lazily call
  `convert_artifact_async(art_id, artifact_path, artifact_type)`; it chains `ensure_converted` →
  `index_artifact_async(md)`. (Covers agent-posted PDFs, which never hit the client path.)
- `src/pathly_orchestrator/runner/hydrate.py` (`:65`, `:198`, `:345`) &
  `runner/hydrate_helpers.py` — resolve `path = resolve_text_source(path)` **before** each
  `_is_md(path)` / `_read_file_text(path)`, so `ensure_indexed`, `hydrate_section`, and the async
  indexer operate on the `.md`. Preserve the original basename for agent-facing display (response
  `artifact` field), not `report.pdf.md`.
- `src/pathly_orchestrator/http_server/blueprints/comms/_summary_request.py:90` — gate on
  `_is_md(resolve_text_source(artifact_path, artifact_type))` and emit the **resolved** `.md` path
  (server-initiated summary arm covers converted docs too).
- `runner/embeddings.py` — only if embedding the full `.md` body (beyond the summary) is wanted.

### Tests
- `context_refs` → a PDF artifact → `_collect_hydrate_channel` returns the converted `.md`'s section
  text. Section-index on a `.docx` yields real `##` sections; on a flat PDF yields whole-file.

### Phase-2 DoD
US-6 passes. A task referencing a converted doc hydrates its text into the agent prompt; the doc is
returned by `/comms/search`.

---

## Phase 3 — Later (not v1)
- OCR for scanned PDFs via the `markitdown-ocr` plugin (reuses the existing LLM client; empty
  Phase-1 output routes here).
- `.xlsx`; table-fidelity supplement (`pdfplumber.extract_tables()` appended for table-heavy PDFs).
- Real `'docx'`/`'pptx'` atype + card icon (touch the 4-way `atype` fork deliberately).
- Whole-document (>8k) map-reduce summarization.

## UI (per designer — rides existing components)
- **Converting/pending state:** reuse the existing `summaryBadge` / `markSummaryStatus` pattern
  between post and summary-ready.
- **Failed / no-text:** toast (`toastStore`) + status, distinct from the silent filename-only path.
- **View converted markdown (Could):** `ArtifactModal` Type row + Preview / Open-in-editor.
- No meaningful net-new design work.
