# TEST_FAILURES — parallel-scout-standard Conv 4 (archive copy)

## Summary

1 NOT COVERED item found. 0 FAIL items. All other criteria PASS.

## NOT COVERED

### S-6 Edge Case 1 — phase: analyze precedence when Scout Findings also present

None of the four agent contracts explicitly state that `phase: analyze` takes precedence when a `## Scout Findings` block is also present in the prompt.

**Required fix:** Add to the `## Phase: analyze` section of each of the four agent contracts:
```
If `## Scout Findings` is also present in the same prompt, `phase: analyze` takes
precedence — output NEEDS_CONTEXT only and ignore the findings block.
```

Files: planner.md, builder.md, reviewer.md, architect.md
