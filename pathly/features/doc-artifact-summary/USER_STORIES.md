# User Stories — Doc Artifact Summary

Acceptance criteria are the testable definition of done. "Converted formats" = `.pdf`, `.docx`,
`.pptx` (v1).

## US-1 — Drop a PDF, get an MD-style summary (core)
> **Given** a board with a summary target configured (not Off),
> **When** I drag a text-bearing `.pdf` onto the Artifacts view,
> **Then** an artifact card appears immediately for the file, and within a few seconds its card
> shows a Description + Summary produced by the *same* summarizer, at the *same* depth, as a
> dropped `.md` — with no extra clicks.

Acceptance:
- Card posts and is visible **before** conversion/summary finish (drop never blocks).
- Extracted markdown is summarized through the existing `summarizeArtifactById` path (same depths,
  same `## Description`/`## Summary` parse, same write-back).
- Depth honors the board's configured style; Off ⇒ filename/title only (unchanged).
- Conversion runs **once at drop**; the derived `.md` is cached (re-summarize does not re-convert).
- A PDF and an `.md` of the same content produce comparable summaries.

## US-2 — Drop Word/PowerPoint, typed and summarized correctly
> **Given** I drop a `.docx` or `.pptx`,
> **When** it posts,
> **Then** it is summarized exactly like US-1, and (polish) is typed/iconed as a document rather
> than `code`.

Acceptance:
- `.docx` and `.pptx` convert + summarize identically to `.pdf`.
- `.pptx` conversion includes slide text + speaker notes.
- Conversion keying is by **extension** — the summarize path does not depend on a new `atype`.

## US-3 — Scanned / text-less file fails gracefully
> **Given** I drop an image-only/scanned PDF (or corrupt/password-protected file),
> **When** conversion yields no usable text,
> **Then** the card **still posts** (I keep my file on the board) and the summary area shows an
> explicit state — e.g. *"No extractable text — looks like a scanned document; OCR isn't supported
> yet"* — never a silent blank or a scary error.

Acceptance:
- Empty/failed conversion → card remains, summary skipped, explicit non-alarming state/toast.
- No empty `.md` sidecar is ever written (would poison Phase-2 indexing).

## US-4 — Re-summarize / change depth (parity)
> **Given** a posted, converted artifact,
> **When** I change summary depth or hit Re-summarize,
> **Then** it behaves identically to a `.md` artifact, re-running the AI over the **cached** derived
> `.md` (no re-conversion, no re-drop).

## US-5 — Multi-file & large-file drops
> **Given** I drop several files at once (mixed `.md`/`.pdf`/`.docx`/`.pptx`/unsupported),
> **Then** each supported file posts + converts + summarizes independently, unsupported files still
> post as plain artifacts (today's behavior), one summary toast is shown; and for a very large
> document I understand the summary reflects the document's front matter (8k-char cap).

## US-6 — Converted docs feed agent context + search (Phase 2, **core for this feature**)
> **Given** a converted `.pdf`/`.docx`/`.pptx` artifact referenced by a task's `context_refs`,
> **When** an agent retrieves board context or a semantic search runs,
> **Then** the document's derived markdown is section-hydratable into the agent prompt (via
> `hydrate_section` reading the resolved `.md`) and semantically searchable like any `.md` artifact.

Acceptance:
- `_collect_hydrate_channel` hydrates the converted `.md`'s text for a PDF/Word/PPT `context_ref`.
- Section-index + embeddings run on the resolved `.md` (docx/pptx get real sections; PDF hydrates
  whole-file — accepted limitation).

## MoSCoW (v1)

| Priority | Item |
|---|---|
| **Must** | `.pdf` (text-bearing), `.docx`, `.pptx` → derived markdown → summarized via the existing shared summarizer at existing depths. |
| **Must** | Card posts instantly; conversion+summary async/best-effort, never block/fail the drop. |
| **Must** | Graceful "no extractable text" state for scanned/empty/corrupt files (card still posts). |
| **Must** | Conversion is **local/offline** — no document content leaves the machine. |
| **Must** | Depth + Re-summarize + per-board note parity with `.md`. |
| **Must** | **Phase 2:** converted docs section-hydratable + embedded → context catalog + semantic search (US-6). |
| **Should** | Cached `.md` reused on Re-summarize (no re-convert). |
| **Should** | Derived `.md` cleaned up when its card is deleted. |
| **Could** | Real `'docx'`/`'pptx'` atype + card icon (`types.ts:48` + both `inferAtype` copies + `guess_artifact_type`). |
| **Could** | "View converted markdown" via `ArtifactModal` Preview / Open-in-editor. |
| **Could** | `.xlsx` (tabular → markdown; often noisy). |
| **Won't (v1)** | OCR / scanned-PDF recovery (later: `markitdown-ocr` plugin). |
| **Won't (v1)** | Image→markdown; legacy `.doc`/`.ppt`/`.xls`; cloud conversion; content-hash dedup; whole-document (>8k) summarization; editing derived `.md` back to source. |
