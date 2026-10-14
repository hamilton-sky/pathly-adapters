## Root-cause debugging

This is not your first try: something failed after an earlier attempt, or after you finished.
Do not guess and do not patch until you know why.

1. **Read every failure above.** Take them in order. Each names a source (a gate, the floor
   guard, a task check, a reviewer or tester) and, where it can, the exact command that failed.
2. **Reproduce it with the exact command.** Run the command the failure names, fresh, and read
   the whole output and the exit code. If you cannot make it fail the same way, you do not yet
   understand it: say so in your report rather than changing code.
3. **Isolate the cause** before you touch anything.
   - Shrink it: the smallest failing case, the one test or one input that shows it.
   - One hypothesis at a time. Say what you expect to see, then check it.
   - Read the code path from the failing line back to where the wrong value or step comes from.
   - Change one thing per experiment, and undo experiments that told you nothing.
4. **Fix the cause, never the check.** Do not make a check pass by weakening it:
   no skipped or deleted tests, no loosened expectations, no silenced linters,
   no edits to lint, test or CI config. The supervisor's floor guard checks this after you
   finish, and a change that weakened the bar is sent back to you.
5. **Prove it.** Re-run the command that failed and see it pass. Then re-run the task's checks
   in full, and only then report the work done.

**When to stop.** After two failed fixes of the same error, stop and report what was tried and
what you saw, instead of trying a third time.
