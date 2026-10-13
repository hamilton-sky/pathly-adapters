# Define the chief tiers and resolve a preset to its tier

Type: task
Status: open
Blocked by: —
Test first: yes

Add `src/pathly_orchestrator/supervisor/chief_tiers.py`, the one place that says what a chief may
do. It is code, never data read from prompt text.

- `ACTIONS = ("read", "post", "plan", "decide", "run", "stop", "answer")`.
- `TIERS`: `status` → `read`; `planner` → `read`, `post`, `plan`; `operator` → all seven.
- `actions_for(tier) -> frozenset[str]`: the tier's actions; an unknown tier gets `status`'s.
- `normalise_tier(value) -> str`: lower-cased and stripped; anything not in `TIERS` is `status`.
- `resolve_preset_tier(preset, project_root) -> str`: if a user prompt file `chief/<preset>`
  exists (look it up with `skills/prompt_files.read_prompt_file`, which already merges project over
  global), its leading front matter's `tier:` value decides through `normalise_tier`, and a file
  with no front matter or no `tier:` is `status`; otherwise the built-in names `status`, `planner`
  and `operator` map to themselves; anything else is `status`. A malformed preset name (anything
  `read_prompt_file` rejects) is `status`.
- `strip_front_matter(text) -> str`: the text with one leading front-matter block removed; reuse
  `skills/compose_base._strip_leading_frontmatter` rather than a second regex.

Parse only a leading `---` block and only its `tier:` line; ignore every other key. This is the
brief's `Decided:` line: each preset names its base style, preset text never grants permissions,
and an unknown or missing style means Status (read-only).

## Not in this ticket

- Using the tier at open time or in the gate: tickets 06 and 08.
- Studio writing `tier:` when the user saves a preset: round two (`map.md` § Round two).
- An editable tier table: dropped (spec.md § Decisions, "Tier table").

## Done when

- `python -m pytest tests/comms_board/test_chief_tiers.py -q -p no:cacheprovider` passes and
  covers: the three action sets; `actions_for("admin")` equals `actions_for("status")`; built-in
  names resolve to themselves with no files present; a project file `chief/operator.md` with no
  front matter resolves to `status`; one with `tier: Planner` resolves to `planner`; one with
  `tier: admin` to `status`; a project file overrides a global file of the same name; an unknown
  preset and a name like `../x` resolve to `status`; `strip_front_matter` removes the block and
  keeps the body.
- `lint-imports` exits 0.

```check
$ python -m pytest tests/comms_board/test_chief_tiers.py -q -p no:cacheprovider
exit 0
prints passed
$ lint-imports
exit 0
```

## Reference

- spec.md § Decisions ("Where permissions come from", "Preset to tier", "Tier table")
- `src/pathly_orchestrator/skills/prompt_files.py` (`read_prompt_file`, `_ID_RE`, file layout
  `pathly/prompts/<category>/<name>.md` and `~/.pathly/prompts/`)
- `src/pathly_orchestrator/skills/compose_base.py::_strip_leading_frontmatter`

## Answer
