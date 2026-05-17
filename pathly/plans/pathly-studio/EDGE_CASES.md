# EDGE_CASES.md — pathly-studio

---

## E1 — projectPath not set

**Situation:** `PROJECT_PATH` env var is empty or missing on first launch.
**Expected:** App opens but sidebar is empty with message "Set project path in Settings". Settings section in sidebar has a text input for the path. Saving it persists to localStorage and re-triggers sidebar load.
**Risk:** Medium — silent failure if not handled.

---

## E2 — File has no YAML frontmatter

**Situation:** A skill or agent markdown file has no `---` frontmatter block (older files).
**Expected:** ConfigForm renders with all fields empty. Saving adds a frontmatter block above the existing content with only the fields the user filled in. Existing content is not touched.
**Risk:** Low — easy to handle with a simple check for `---`.

---

## E3 — YAML frontmatter contains unknown keys

**Situation:** A file has frontmatter with keys ConfigForm doesn't know (e.g. `version`, `model`).
**Expected:** Unknown keys are preserved as-is in the frontmatter on save. ConfigForm shows them as read-only `key: value` text. They must not be silently dropped.
**Risk:** High — dropping keys would corrupt adapter YAML configs silently.

---

## E4 — Flow YAML parse error in Visual tab

**Situation:** The YAML file has invalid syntax or missing required fields.
**Expected:** Red error banner above the Visual tab: "YAML parse error: `<message>`". Visual view shows empty canvas. YAML tab still loads the raw content so the developer can fix it.
**Risk:** Medium — app must not crash on bad YAML.

---

## E5 — MCP server not running

**Situation:** Monitor opens, MCP ping times out (> 500ms).
**Expected:** Silently falls back to file watch. Badge shows `○ File watch`. No error dialog.
If file watch also fails (no STATE.json for the topic): shows "No state file found for `<topic>`. Run the pipeline first."
**Risk:** Low — expected scenario for LLM-driven mode users.

---

## E6 — Concurrent edit (file changed on disk while editor is open)

**Situation:** Claude/Codex writes to a skill file while the developer has it open in the editor with unsaved changes.
**Expected:** App does not auto-reload (would discard unsaved changes). A banner appears: "File changed on disk — [Reload] [Keep mine]". Reload discards local changes; Keep mine keeps them until next Save.
**Risk:** Medium — this will happen during active pipeline runs.

---

## E7 — Publish fails (pip error)

**Situation:** `pip install -e .` exits with non-zero code.
**Expected:** "Publish failed" banner stays visible. Log panel stays open showing the error output. Publish button re-enables after failure. Developer can fix the issue and retry.
**Risk:** Low — but failure must be clearly communicated, not silently swallowed.

---

## E8 — Write rejected (path outside projectPath)

**Situation:** A bug causes a write attempt to a path outside the project root (e.g. `/etc/passwd`).
**Expected:** Main process rejects the write with an error. Renderer shows "Write rejected: path outside project". This is the security guard in `ipc/fs.ts`.
**Risk:** Low probability but high severity — must be enforced.

---

## E9 — Very large EVENTS.jsonl

**Situation:** A long-running topic has thousands of events in EVENTS.jsonl.
**Expected:** Watcher reads only the last 50 lines (tail). EventLog renders only those 50. No memory issue from parsing the entire file.
**Risk:** Low — if not handled, could cause renderer lag on large projects.
