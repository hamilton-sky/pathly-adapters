## Pulling context from the Board Catalog

Your prompt's board context already pushes you the curated channels — 🔒 governance,
📎 the task's referenced sections, and 💡 semantic matches. When the task needs more than
those, you may **pull** additional artifacts from the board catalog. You are scoped to your
own board, so this is safe and bounded — you cannot see another feature's artifacts.

The 📚 **Catalog** block in your context lists the top artifacts inline (path · type · summary).
Read that first and pull only the section you actually need — do not refetch the 📎 references,
they are already hydrated.

### How to pull

```bash
# List what's available on your board (already permission-scoped to you)
curl -s "http://127.0.0.1:8765/comms/artifacts?board=feature&scope=<feature>"

# Read one section (omit &anchor for the whole file)
curl -s "http://127.0.0.1:8765/comms/artifacts/section?scope=<feature>&artifact=<path>&anchor=<anchor>&trail=<task_id>"
```

Read the returned `text` field — it is the authoritative section, not the `summary`.

### Rules

- **Pull narrowly.** Only fetch what the current task needs; the catalog is large by design.
- **Record what you read.** Append `&trail=<task_id>` to a section pull so the board logs the
  access — this is how the timeline shows what context each task consumed.
- **Advisory + skip-if-down.** If the server is unreachable, skip silently and proceed from the
  context you already have. Pulling never blocks your work.
- **Don't refetch 📎 references** — they are already in your prompt.
