## Build discipline — the laziest solution that survives review

Run this AFTER you understand the problem, never instead of it. Trace the real flow
end to end first — every file the change touches — then climb. Laziness shortens the
solution, never the reading; a small diff in the wrong place is a second bug.

**The ladder — stop at the first rung that holds.** The highest working rung wins.

1. **Does this need to exist at all?** Speculative need → skip it, say so in one line. (YAGNI)
2. **Already in this codebase?** A helper, type, util, or pattern a few files over → reuse it. Re-implementing what already exists is the most common slop — the scout phase exists to find it, so use those findings before you write.
3. **Standard library does it?** Use it. Name the function.
4. **Native platform feature covers it?** DB constraint over app code, CSS over JS, a built-in over a new dependency.
5. **An already-installed dependency solves it?** Use it. Never add a new dependency for what a few lines do.
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

**Bug fix = root cause, not symptom.** A report names a symptom. Before you edit, find
every caller of the function you're about to touch (prefer the code-graph / LSP tools —
`impact` / `callers`). One guard in the shared function is a smaller diff than a guard in
every caller — and patching only the path the ticket names leaves every sibling caller
still broken. Fix it once, where all callers route through.

**House rules are the binding constraint — laziness never overrides them.** The ladder
decides how *small* the change is; the project conventions file (CLAUDE.md and any linked
rules) decides which changes are *valid* — layer/dependency direction, file-size limits,
module boundaries, and the frontend component-folder layout. "Simplest" always means
"simplest that still obeys the house rules." When the two pull apart, the house rules win
and you note the tension in one line — never silently break a documented contract to save
a line.

**Mark deliberate shortcuts with a `ponytail:` comment.** A shortcut with a known ceiling
names the ceiling and the upgrade trigger — `# ponytail: global lock, per-account locks if
throughput matters`. Simple reads as intent, not ignorance, and the marker turns a silent
deferral into a tracked one instead of "later means never". This is the one exception to
"default to no comments": a `ponytail:` marker is a WHY, not a WHAT.

**When NOT to be lazy.** Never simplify away input validation at trust boundaries, error
handling that prevents data loss, security measures, accessibility basics, or anything the
task explicitly asked for. Non-trivial logic (a branch, a loop, a parser, a money/security
path) leaves ONE runnable check behind — the smallest thing that fails if the logic breaks
(an `assert`-based self-check or one small `test_*`), no frameworks. Trivial one-liners need
no test; YAGNI applies to tests too.

Keep the report shorter than the diff. Every paragraph defending a simplification is
complexity smuggled back in as prose — the exception is explanation the task explicitly
asked for (a walkthrough, per-phase notes), which is the deliverable, not debt.
