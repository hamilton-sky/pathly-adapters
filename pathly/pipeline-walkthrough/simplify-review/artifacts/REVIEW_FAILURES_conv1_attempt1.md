# Review Failures — Conv 1

## [IMPL] docs/ARCHITECTURE.md — broken relative link

**Location:** `docs/ARCHITECTURE.md`, line added in "What Gets Installed" section

**Violation:**
```
See [FLOW_DIAGRAM.md](docs/FLOW_DIAGRAM.md) for the full command reference and deployed file details.
```
`ARCHITECTURE.md` is inside `docs/`. A relative link of `docs/FLOW_DIAGRAM.md` resolves to
`docs/docs/FLOW_DIAGRAM.md` — a broken path.

**Fix required:**
Change `docs/FLOW_DIAGRAM.md` → `FLOW_DIAGRAM.md` so the relative link resolves correctly
from within the `docs/` folder.
