## Transforming an artifact

Read the source artifact at `<source_path>` exactly once, derive a **<transform_kind>** of it, and
write the derived result to `<out_path>` (see the file-output rules above).

Rules:
- The source is **read-only** — never modify `<source_path>`.
- The output is **write-once** — never read `<out_path>` back as input.
- Produce **only** the derived result — no preamble, no commentary, no wrapping the whole document
  in a code fence.
- Write the file as **UTF-8 using your native file-writing tool**. Do NOT route content through shell
  commands (`Get-Content`/`Set-Content`/`Out-File` or `>` redirection) — on Windows PowerShell they
  corrupt Unicode into mojibake (`—` becomes `â€"`). Preserve every character byte-for-byte,
  including Unicode punctuation (em-dash —, en-dash –, curly quotes, ellipsis …).
