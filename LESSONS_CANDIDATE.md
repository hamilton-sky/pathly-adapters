# Lessons Candidate

Extracted from completed features. Run `/pathly lessons` to promote to active memory.

---

## From: studio-ai-chat (2026-05-27)

- **Acceptance criteria enforce pipeline discipline.** Explicit AC for each story made scope violations obvious and gave reviewers unambiguous gate signals. Without AC, 3 scope gate failures would have become subjective arguments.

- **Static schema beats runtime scanning.** Building a typed, constant `studioSchema.ts` instead of parsing the DOM at runtime eliminated a class of flaky automation bugs and made element mapping fully testable without mocking the browser.

- **Embedding models buy responsiveness for free.** MiniLM (transformers.js) delivered sub-50ms skill matching with zero server cost — and doubled as the automation label-matcher in Conv 7's 3-tier cascade.

- **Scope gates need exemption rules for build artifacts.** `tsconfig.tsbuildinfo` and generated type files should never trigger scope violations. Add a category filter to the gate before the first review cycle — 6 gate failures over 5 conversations wasted orchestration time.

- **Budget AI context tokens early.** By Conv 6, every chat request included FSM state + skills list + studioSchema. Agree on a context budget in Conv 0 to prevent bloat before it hits token limits.
