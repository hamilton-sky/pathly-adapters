# Pathly — Seed Data

What gets inserted into `~/.pathly/pathly.db` the first time the app opens (if tables are empty).

---

## Flow definitions

### `team` — full pipeline
```sql
INSERT INTO flow_definitions VALUES (
  'team', 'Team', 'Full pipeline: build → review → test loop', 'standard', 1,
  NULL, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
);
```

Nodes:
| name | agent_role | skill_name | adapter | pos_x | pos_y |
|---|---|---|---|---|---|
| BUILD | builder | pathly-build.md | claude | 100 | 200 |
| REVIEW | reviewer | pathly-review.md | claude | 350 | 200 |
| TEST | tester | pathly-test.md | claude | 600 | 200 |
| RETRO | planner | pathly-retro.md | claude | 850 | 200 |

Edges:
| from | to | condition |
|---|---|---|
| BUILD | REVIEW | PASS |
| BUILD | BUILD | FAIL |
| REVIEW | TEST | PASS |
| REVIEW | BUILD | FAIL |
| TEST | RETRO | PASS |
| TEST | BUILD | FAIL |

---

### `standard` — build + review only
Nodes: BUILD → REVIEW → TEST
Edges: BUILD--PASS→REVIEW, BUILD--FAIL→BUILD (max 3), REVIEW--PASS→TEST, REVIEW--FAIL→BUILD

---

### `nano` — single conversation, no review
Nodes: BUILD only
Edges: none (exits when BUILD returns PASS)

---

### `plan-only` — planning stages
Nodes: STORM → PLAN → DESIGN
Edges: unconditional chain

---

## Skill definitions (global, `project_root = NULL`)

All seeded from `src/pathly_data/skills/` content. `is_custom = 0`.

| id | file_name | display_name | category | compatible_stages |
|---|---|---|---|---|
| `pathly-build` | `pathly-build.md` | Build | build | `["BUILD"]` |
| `pathly-review` | `pathly-review.md` | Review | review | `["REVIEW"]` |
| `pathly-review-strict` | `pathly-review-strict.md` | Review (Strict) | review | `["REVIEW"]` |
| `pathly-review-lite` | `pathly-review-lite.md` | Review (Lite) | review | `["REVIEW"]` |
| `pathly-test` | `pathly-test.md` | Test | test | `["TEST"]` |
| `pathly-plan` | `pathly-plan.md` | Plan | plan | `["PLAN"]` |
| `pathly-storm` | `pathly-storm.md` | Storm | plan | `["STORM"]` |
| `pathly-retro` | `pathly-retro.md` | Retro | plan | `["RETRO"]` |
| `pathly-fix` | `pathly-fix.md` | Fix | build | `["BUILD"]` |
| `pathly-explore` | `pathly-explore.md` | Explore | plan | `["STORM","PLAN"]` |

Content for each: read from `src/pathly_data/skills/<file_name>` at seed time.

---

## Agent definitions (global, `project_root = NULL`)

All seeded from `src/pathly_data/agents/` content. `is_custom = 0`.

| role | display_name | model |
|---|---|---|
| `builder` | Builder | `claude-sonnet-4-6` |
| `reviewer` | Reviewer | `claude-sonnet-4-6` |
| `tester` | Tester | `claude-sonnet-4-6` |
| `planner` | Planner | `claude-sonnet-4-6` |
| `architect` | Architect | `claude-opus-4-5` |
| `explorer` | Explorer | `claude-sonnet-4-6` |
| `director` | Director | `claude-sonnet-4-6` |
| `designer` | Designer | `claude-sonnet-4-6` |
| `po` | Product Owner | `claude-sonnet-4-6` |
| `quick` | Quick | `claude-haiku-4-5` |
| `scout` | Scout | `claude-haiku-4-5` |
| `orchestrator` | Orchestrator | `claude-haiku-4-5` |

Instructions for each: read from `src/pathly_data/agents/<role>.md` at seed time.

---

## Seed function (Python pseudocode)

```python
def seed_app_db(db: sqlite3.Connection):
    """Run once if tables are empty. Idempotent — uses INSERT OR IGNORE."""

    # 1. seed flows
    for flow in FLOW_DEFINITIONS:
        db.execute("INSERT OR IGNORE INTO flow_definitions ...")
        for node in flow.nodes:
            db.execute("INSERT OR IGNORE INTO flow_nodes ...")
        for edge in flow.edges:
            db.execute("INSERT OR IGNORE INTO flow_edges ...")

    # 2. seed skills from pathly_data/
    skills_dir = Path(__file__).parent.parent / "pathly_data" / "skills"
    for md_file in skills_dir.glob("*.md"):
        content = md_file.read_text()
        skill_id = md_file.stem  # e.g. "pathly-build"
        db.execute("INSERT OR IGNORE INTO skill_definitions ...", (
            skill_id, md_file.name, ..., content, ..., None, 0
        ))

    # 3. seed agents from pathly_data/
    agents_dir = Path(__file__).parent.parent / "pathly_data" / "agents"
    for md_file in agents_dir.glob("*.md"):
        role = md_file.stem
        instructions = md_file.read_text()
        db.execute("INSERT OR IGNORE INTO agent_definitions ...", (
            role, ..., instructions, ..., None, 0
        ))

    db.commit()
```

---

## When to run seed

Called from `http_server.py` startup, after `_ensure_schema()`:

```python
def startup():
    db = get_db()
    _ensure_schema(db)   # CREATE TABLE IF NOT EXISTS
    _seed_if_empty(db)   # INSERT OR IGNORE — idempotent
```

`INSERT OR IGNORE` means re-running seed never overwrites user-edited content.
To force a re-seed (e.g. after updating built-in skills): delete the row first, then re-run.
