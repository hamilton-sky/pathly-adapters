## Searching the board

Your prompt's board context was assembled from ONE query the runner wrote for you — it
embedded your task description and took the top few matches per tier. That is a good first
guess, but it is a guess: it was computed before you read the task, and it cannot know the
term you are about to trip over.

When it comes up short, **ask the board yourself, in your own words**. This is the same
hybrid (keyword + semantic) index the injected context came from — you are re-querying it
with a better question, not reading a different store.

### When to search

Search when the answer plausibly already exists on the board and you do not have it:

- The injected context is thin, or it matched your task's topic but not the part you are
  actually stuck on.
- You hit a term, constraint, or name that reads like a prior decision you were not shown.
- You are about to make a choice someone may already have made — search before deciding,
  not after.

Do **not** search:

- Before reading what you were already given. The pushed channels come first, always.
- To re-fetch a reference or catalog entry that is already in your prompt.
- More than a few times for one task. Two or three targeted queries is a working session;
  ten is a sign you should proceed with what you have and say what was missing.

### How to search

```bash
curl -s -X POST http://127.0.0.1:8765/comms/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "<what you actually want to know, in plain words>",
    "feature": "<feature>",
    "board": "<board>",
    "scope": "<feature>",
    "k": 5
  }'
```

- `query` — a phrase, not a keyword. `"why does the runner spawn codex with null stdin"`
  beats `"codex stdin"`: the semantic arm matches meaning, so a fuller question ranks better.
  Capped at 512 characters.
- `k` — how many results (default 5, max 50). Start at 5; raise it only if 5 came back all
  relevant and you need more of the same.
- `mode` — optional: `hybrid` (default, use this), `keyword` for an exact literal string,
  `semantic` when you want meaning-matches only.
- You are scoped to your own board. Cross-tier (project / global) context reaches you
  through the injected channels, which are governed by the run's board-scope setting.

### Reading the results

The response is a JSON array of board messages, best-first. Per result:

- `text` — the message. This is the content; read it.
- `_match_source` — `keyword` (a literal match) or `semantic` (a meaning match). A keyword
  hit is a stronger signal that you found the exact thing you named.
- `_distance` — cosine distance on semantic hits, lower is closer. Absent on keyword hits.
- `type` — `decision` and `constraint` outrank `discovery` and `status`: a decision binds
  you, a discovery merely informs you.

**An empty array means the board genuinely has nothing** — results are never padded with
recent messages, so `[]` is a real answer, not a failure. Take it at face value, stop
searching for that thing, and proceed. If what you needed was missing, say so in your
output; that gap is itself worth recording.

### Rules

- **Search reads, it never writes.** Finding something does not mean re-posting it — it is
  already on the board. Post only what YOU produced.
- **A search result is context, not authority.** Governance in your prompt still wins, and
  your own output file remains the source of truth for your work.
- **Advisory + skip-if-down.** If the server is unreachable or returns non-200, skip
  silently and proceed from the context you already have. Searching never blocks your work.
