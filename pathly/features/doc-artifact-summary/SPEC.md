# Feature: Doc Artifact Summary (PDF / Word / PowerPoint → board summary)

**Status:** SPEC (pre-build) · **Scope:** feature · **Depends on:** comms-board, unified-ai-routing

## Goal

Let a user drag a **PDF, Word (`.docx`), or PowerPoint (`.pptx`)** file onto the board's
Artifacts view and have it summarized — and made board-first-class — the **same way a dropped
`.md` file already is**. The dropped file becomes an artifact card, its content is converted to
markdown behind the scenes, and the existing target-agnostic summarizer + context-catalog
hydration operate on that markdown.

## Background — the current mechanism and the gap

The drop → post → summarize path is already real and tight (traced end-to-end):

- **Drop** `ArtifactsView.tsx:57 handleDrop` accepts any OS file (no extension filter) →
  `onDropFiles`. **PDFs already post as artifact cards today.**
- **Ingest** `CommsPanel.tsx:151 handleDropFiles`: copies the file into `<board>/artifacts/`,
  `atype = inferAtype(name)` (`CommsPanel.tsx:42` — returns `'pdf'`; **`.docx`/`.pptx` wrongly
  fall through to `'code'`**), `apiPostArtifact(..., 'minilm')` posts the card (`minilm`
  suppresses the server summarizer), then fires `void summarizePosted(...)` — **already
  detached**, so the drop never blocks on the summary.
- **Summarize** `ArtifactsView/summarizeArtifact.ts`: gate `isSummarizable` (`:28`) = md/markdown/txt
  only; body `summarizeArtifactById` (`:84`) does `readFile(abs)` as **UTF-8 text** (`:99`) → a
  binary PDF/docx reads as garbage. Then aiRouter `runJob` runs the user's chosen target — a
  **target-agnostic** summarizer (local GGUF/Ollama model **or** a claude/codex CLI engine). This
  is why "just send the PDF to Claude" does not generalize: the summarizer input must be plain
  text/markdown any target can read.
- **Context catalog** `comms_context.retrieve_board_context` → `comms_formatters._collect_hydrate_channel`
  (`:110`) hydrates a task's `context_refs` into agent prompts as **full section text** via
  `hydrate_section` — gated `.md`-only (`hydrate.py:198`). Same `.md` gate also governs
  section-indexing (`hydrate.py:65,345`) and embeddings/semantic search.

**The gap:** everything downstream reads a **text** file. PDFs/Word/PPT never produce one. So the
single missing primitive is a **document → markdown** conversion step whose output the existing
summarizer + catalog read.

## Design (decisions locked)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | **Canonical artifact** | **Original file is the card; `.md` is invisible text-source plumbing** | Clean provenance — agents cite `report.pdf`, user opens the PDF. Identity (PDF) is cleanly separated from text-source (`.md`) by one resolver. |
| D2 | **Converter** | **Microsoft `markitdown`** | Thin MIT wrapper over `pdfplumber`(PDF)+`mammoth`(docx)+`python-pptx`(pptx) — the exact libs already in the tree; no ML weight. One call for all three formats: `MarkItDown().convert(path).text_content`. |
| D3 | **Dependency posture** | **Bundle out-of-the-box** (`markitdown[pdf,docx,pptx]` in the app env) **+ lazy import** | Every user gets summaries by default; a partial dev install degrades to today's "card, no summary" instead of crashing. |
| D4 | **Conversion locus** | **Python, `runner/` layer**, one idempotent core `ensure_converted(path) → md_path|None` | Phase 2 (index/hydrate/embeddings) is server-side and consumes the `.md`; converter ecosystem is Python; `runner/` already owns hydrate/sections/embeddings and imports only `db/`. |
| D5 | **Client↔server contract** | **Synchronous, idempotent `POST /comms/artifacts/convert`**, client-awaited inside the already-detached summary chain — **not** async-daemon+poll | The drop is already non-blocking (`void summarizePosted`), so async+poll buys nothing but a race window and a second summary trigger. Sync + awaited is race-free and keeps the single `minilm`-guarded summary path. |
| D6 | **Sidecar identity** | **Convention `<path>.md`** (append, e.g. `report.pdf.md`) | Zero migration; matches `.summary`/`.split.draft` conventions; append avoids colliding with a real `report.md`; DB `path` stays the original. |
| D7 | **Anti-fork** | One `resolve_text_source(path)` inserted **in front of** each gate; gate predicates unchanged | The "3 gates" are really 2 predicates (hydrate is `.md`-only, no txt). Resolving in front keeps hydrate from silently indexing `.txt` while letting a resolved `report.pdf.md` pass. |
| D8 | **Trigger key** | **File extension, not `atype`** | Touches none of the 4-way `atype` fork (`inferAtype` ×2, `guess_artifact_type`); the core feature needs no new `docx`/`pptx` atype (that's optional icon polish). |
| D9 | **Failure model** | Every failure → **HTTP 200 `{ok:false, reason}`**; never write an empty `.md` | Best-effort, never blocks the drop. Reasons: `converter_missing` / `conversion_failed` / `empty_output` / `too_large` / `not_found`. |

### Flow

```
PHASE 1 (drop) — client-owned summary, server-owned conversion
 copy → apiPostArtifact('minilm') ── card appears (reload) ──▶ drop returns (NOT blocked)
            └─ void summarizePosted → summarizeArtifactById
                 resolveTextSource(abs, atype)
                   ├ text ext ─────────────▶ abs
                   └ pdf/docx/pptx → POST /comms/artifacts/convert (sync, idempotent)
                                          server ensure_converted(abs) ─atomic▶ abs.md
                 readFile(abs.md) → runJob(target) → apiSetArtifactSummary   [UNCHANGED]

PHASE 2 (catalog / index / embeddings / agent-posted docs) — same core, different trigger
 /comms/post ─▶ convert_artifact_async(daemon) → ensure_converted(abs)
                    └▶ index_artifact_async(abs.md) + emit_summary_request(abs.md) + embeddings
 hydrate_section / _is_md gates ─▶ read resolve_text_source(path)  → PDFs hydrate into agent prompts
```

## Converter — markitdown (verified)

`markitdown` v0.1.7 (2026-07-29, MIT, Python ≥3.10). API: `MarkItDown().convert(path).text_content`
(construct fresh per call — thread-safety is undocumented, construction is cheap). Exceptions:
`MissingDependencyException`, `UnsupportedFormatException`, `FileConversionException` (base
`MarkItDownException`). Extras: `pdf` = `pdfminer.six`+`pdfplumber`, `docx` = `mammoth`+`lxml`,
`pptx` = `python-pptx`. **No ML deps.**

Known limits (accepted for v1): weak PDF **table** fidelity (open upstream issues; supplement with
`pdfplumber.extract_tables()` later if summaries suffer); **slow on large PDFs** (pdfminer is
synchronous — pair with a size cap); **no built-in OCR** → scanned/image-only PDFs yield empty
text (→ `empty_output`; OCR via the `markitdown-ocr` plugin is a later phase).

## Scope

**v1 formats:** `.pdf`, `.docx`, `.pptx`. **In:** local-only conversion; depth / re-summarize /
per-board-note parity with `.md`; card posts instantly; graceful "no extractable text" state;
Phase-2 catalog hydration + search for converted docs.

**Non-goals (v1):** OCR / scanned-PDF recovery; image→markdown (images stay `image`,
unsummarized); `.xlsx` (noisy for summaries — later "Could"); legacy `.doc`/`.ppt`/`.xls`; cloud
conversion; content-hash dedup; whole-document (>8k-char) summarization; editing the derived `.md`
back into the source.

## Risks / open items

1. **8k truncation** (`summaryPrompt.ts:15`) — the MODEL target truncates to 8k chars, so a long
   doc's summary reflects its front matter; the CLI-engine target reads the whole file. Accepted +
   named for v1; whole-doc map-reduce is later. (Search/hydration cover the whole doc regardless.)
2. **PDF section granularity** — flat text (no `##`) collapses PDF hydration to whole-file; docx/pptx
   keep headings. Accept; heading-heuristic later.
3. **Derived-`.md` lifecycle** — clean up the sidecar when its card is deleted (no owner today).
4. **Sync convert holds a Flask worker** for the convert duration — fine at low drop volume; cap
   convert concurrency if large multi-file drops become common.

## Definition of done

Drop a text-bearing `.pdf`/`.docx`/`.pptx` → a card appears immediately → within seconds it shows a
Description + Summary from the same summarizer, at the same depth, as a dropped `.md`, with zero
extra clicks. A scanned/empty/corrupt file still posts, with an explicit "no extractable text"
state. (Phase 2) the converted doc is section-hydratable into agent context and semantically
searchable.

See [USER_STORIES.md](USER_STORIES.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
