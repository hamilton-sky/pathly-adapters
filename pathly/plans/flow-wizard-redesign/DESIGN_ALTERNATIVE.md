# FlowWizard — Alternative Design Proposal

## Core principle

Technical users don't trust wizards. They want to see the output forming as they work, not just at the end.
The plan is good — these are three targeted changes on top of it that address that trust problem.

---

## Difference 1: Persistent YAML sidebar (Steps 1–5)

**What the plan does:** YAML preview appears only on Step 5 (Review).

**What I'd do:** A 280px sidebar panel sits to the right of the form content on every step from 1 onwards. It shows the live YAML updating in real time as fields change.

```
┌─────────────────────────────────────────────────────────┐
│  [●●●●●●]  Step 3 of 5 — Assign agents                  │
├──────────────────────────────┬──────────────────────────┤
│                              │  LIVE YAML        ● live │
│  Assign agents               │─────────────────────────│
│  Map a role to each          │  name: feature-pipeline  │
│  non-terminal state.         │  states:                 │
│                              │    - id: STORMING        │
│  ⚠ REVIEWING has no agent   │      agent: architect    │
│                              │    - id: PLANNING        │
│  STORMING  [architect    ]   │      agent: planner      │
│  PLANNING  [planner      ]   │    - id: BUILDING        │
│  BUILDING  [builder      ]   │      agent: builder      │
│  REVIEWING [unassigned…  ]   │    - id: REVIEWING       │
│  TESTING   [tester       ]   │      # ⚠ no agent        │
│  DONE      terminal          │    - id: TESTING         │
│                              │      agent: tester       │
│                              │    - id: DONE            │
│                              │      terminal: true      │
├──────────────────────────────┴──────────────────────────┤
│  Back   [Start over] [Save draft] [Cancel]   [Next →]   │
└─────────────────────────────────────────────────────────┘
```

**Why:** A user who reaches Step 3 and wonders "is the agent field going where I think?" can answer that question immediately without navigating away. The sidebar also **mirrors warnings** — if REVIEWING has no agent, the YAML shows `# ⚠ no agent` next to it inline. Two signals, same information, one glance.

**Sidebar behavior per step:**

| Step | What the sidebar shows |
|---|---|
| 1 — Name | `name:` field updates on keystroke. States/transitions shown as `# fill in step 2` comments |
| 2 — Stages | `states:` block grows as states are added. Agents shown as `# step 3` comment |
| 3 — Agents | `agent:` fields fill in live. Missing agents show `# ⚠ no agent` |
| 4 — Quality | `transitions:` block populates as rules are added |
| 5 — Review | Same sidebar, label changes to "Final YAML" with a green `● complete` dot |

**Modal width:** Grows from 600px (narrow, Steps 0) to 880px (with sidebar, Steps 1–5).

---

## Difference 2: Template gallery visible on Step 0

**What the plan does:** Three equal cards — "From template", "From name", "Start blank". Clicking "From template" reveals the template picker (unclear from the plan where this happens).

**What I'd do:** The template cards are visible **immediately** on Step 0, below the two main path buttons. No second click needed to see what's available.

```
┌──────────────────────────────────────────────────────┐
│  New flow                                            │
│                                                      │
│  ┌────────────────────────┐  ┌─────────────────────┐ │
│  │ 📋 Start from template │  │ ⬜ Start blank       │ │
│  │ Pre-filled stages for  │  │ Define every stage  │ │
│  │ common workflows       │  │ yourself            │ │
│  └────────────────────────┘  └─────────────────────┘ │
│                                                      │
│  CHOOSE A TEMPLATE                                   │
│  ┌──────────────────────┐  ┌────────────────────┐   │
│  │ Standard pipeline ✓  │  │ Review loop        │   │
│  │ STORMING PLANNING    │  │ DRAFTING REVIEW    │   │
│  │ BUILDING REVIEWING   │  │ DONE               │   │
│  │ TESTING DONE         │  └────────────────────┘   │
│  └──────────────────────┘                           │
│  ┌──────────────────────┐  ┌────────────────────┐   │
│  │ Debug cycle          │  │ Blank              │   │
│  │ REPRODUCING          │  │ No pre-fills       │   │
│  │ DIAGNOSING FIXING    │  └────────────────────┘   │
│  │ DONE                 │                           │
│  └──────────────────────┘                           │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ ↩  Resume draft — feature-pipeline           │   │
│  │    Saved 2 min ago · Step 2 · 5 states    [Resume]│
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  [Cancel]                       [Use Standard →]    │
└──────────────────────────────────────────────────────┘
```

**Why:** The template names alone ("Standard pipeline", "Review loop") are not self-explanatory to a new user. Showing the actual state names — STORMING, PLANNING, BUILDING — gives them enough context to choose confidently. The extra click in the plan's design adds friction at exactly the moment the user is most uncertain.

**Interaction rules:**
- Clicking a template card selects it (highlighted border) and updates the CTA button label: "Use Standard pipeline →"
- Clicking "Start blank" deselects any template and changes CTA to "Start blank →"
- "Start from a template" header button selects the first template by default
- Resume draft card only appears when a valid draft file is detected on disk

---

## Difference 3: Completed step dots are clickable

**What the plan does:** Dots are display-only. Navigation is strictly Back/Next.

**What I'd do:** Once a step is completed (dot turns green with checkmark), it becomes a clickable navigation link. Clicking it jumps directly to that step without losing any later state.

```
  ↩  ──  1  ──  2  ──  3  ──  4  ──  5
(back)  (done)  (done)  (active)         ← dots 0–2 are clickable
```

**Why:** A user on Step 4 who realizes a stage name is wrong should not need to press Back twice. Clicking dot `2` takes them directly to Define stages. When they click Next again it returns them to Step 4 with all intermediate state preserved.

**Rules:**
- Future steps (not yet visited) remain non-clickable
- Dot 0 (entry/back icon) always navigates to Step 0 (existing Back behavior)
- No confirmation required when navigating backwards via dot
- Cursor changes to `pointer` on hover; subtle scale(1.1) transform

---

## Progress bar addition (minor)

A 2px progress bar sits above the step indicator, filling left-to-right as steps are completed. It turns green when Step 5 is reached. This gives a second visual progress signal for users who don't read dot numbers.

```
████████████████░░░░░░░░░░░  60% (Step 3 active)
```

---

## Step 5 summary panel

Instead of jumping straight to a YAML block on Step 5, show a brief human-readable **summary checklist** in the left pane before the save path, with the YAML in the persistent sidebar:

```
✓  Name:        feature-pipeline
✓  Stages:      STORMING → PLANNING → BUILDING → ... → DONE
⚠  Agents:      REVIEWING has no agent — flow may stall
✓  Transitions: 1 rule
✓  Quality:     No gates or routing configured

Save to: [~/.pathly/flows/feature-pipeline.yaml      ]
```

The warning on `⚠ Agents` is non-blocking — user can still save. The CTA is still "Save Flow". But seeing the issue listed plainly on Step 5 gives one last chance to notice it without having to read the raw YAML.

---

## What stays exactly as planned

These decisions in the plan are correct — no changes:

| Feature | Keep as-is |
|---|---|
| 6-step model (0–5) | Yes |
| Step 0 hidden from progress counter | Yes |
| Quality & Routing as accordion, all collapsed by default | Yes |
| "optional" semantic on Step 4 | Yes |
| Drag-to-reorder in Step 2 | Yes |
| Cancel confirmation on Step 1+ | Yes |
| Start over button + confirmation | Yes |
| Save draft / Resume draft | Yes |
| Animated checkmark on completed dots | Yes |
| `prefers-reduced-motion` respected | Yes |
| YAML output format unchanged | Yes |

---

## Implementation delta vs. the plan

The three differences above require only additive changes to what the plan already describes:

| Change | Files affected | Effort |
|---|---|---|
| Persistent YAML sidebar | `FlowWizard.tsx` (layout), `FlowWizard.styles.ts` (split grid) | ~1 conversation |
| Template gallery on Step 0 | `Step0Entry.tsx`, `wizardTemplates.ts` | ~0.5 conversation (Step0Entry already planned) |
| Clickable completed dots | `StepIndicator.tsx` | ~30 lines |
| Progress bar | `FlowWizard.styles.ts`, `FlowWizard.tsx` | ~20 lines |
| Step 5 summary panel | `Step5Review.tsx` | ~1 hour |

None of these touch the YAML output format, the validation logic, or the draft persistence system.
