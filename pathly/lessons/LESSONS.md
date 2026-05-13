# LESSONS.md — Active

_Last updated: 2026-05-11 | Sources: 1 feature (security-fixes)_
_Max 12 lessons. Planner reads this before every plan._

> **Note:** Lessons require 2+ source features to be promoted. The entries below are
> single-source candidates from `security-fixes`. They will be promoted to full lessons
> once a second feature confirms the pattern.

---

## CANDIDATE-001: Acceptance criteria for docs stories over-specify format

### Pattern
Planner writes acceptance criteria that mix document structure ("use Risk/Mitigation format") with content requirements, causing test failures when the format criterion doesn't match the existing doc style.

### Rule
Docs stories must specify WHAT content to add as acceptance criteria; HOW it is formatted belongs in the conversation prompt, not the story.

### Injection
- In USER_STORIES.md for any story touching a docs file: keep criteria to verifiable content facts (section exists, vector described, mitigation described) — not format or style rules.

### Sources
security-fixes | Stage: test

---

## CANDIDATE-002: Redundant acceptance criteria confuse the tester

### Pattern
A story criterion that is logically implied by another criterion in the same story gets written explicitly, causing the tester to flag it as NOT COVERED when the implementation satisfies the root criterion but not the redundant one.

### Rule
Each acceptance criterion must be independently falsifiable — if criterion B is always true when criterion A is true, drop B.

### Injection
- Before writing CONVERSATION_PROMPTS.md: scan each story's acceptance criteria for implied/redundant entries and remove them.

### Sources
security-fixes | Stage: test

---

## CANDIDATE-003: Security features need explicit failure-case test criteria

### Pattern
Security fixes without an explicit failure-mode acceptance criterion (e.g. "request with X causes Y") pass implementation review but leave the tester verifying only the happy path.

### Rule
Every security story must include at least one acceptance criterion that describes a specific attack input and its expected output.

### Injection
- In USER_STORIES.md for any security story: add one criterion of the form "A request/input with [bad value] causes [safe outcome]."

### Sources
security-fixes | Stage: planning

---

## CANDIDATE-004: Pre-existing broken tests should be flagged at pipeline start

### Pattern
A test that was already broken before the feature started causes the tester stage to fail, requiring an unplanned builder fix and blurring accountability between the feature and prior debt.

### Rule
Run the test suite once at pipeline start (before Conversation 1) and record any pre-existing failures so they are not attributed to the feature.

### Injection
- In IMPLEMENTATION_PLAN.md for any feature: add a "pre-flight" step — run the verify command and record failures as known baseline before any implementation begins.

### Sources
security-fixes | Stage: test
