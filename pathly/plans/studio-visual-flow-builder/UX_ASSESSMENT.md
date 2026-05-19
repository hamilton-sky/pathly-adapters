# UX/Design Assessment — studio-visual-flow-builder

> Assessed via UI/UX Pro Max design intelligence. Stack: React + Electron + React Flow + CodeMirror.
> Style target: operational IDE (dense, precise, tool-like). Date: 2026-05-19.

---

## Verdict up front

The plan is **UX-solid and safe to implement as written.** The 3-pane layout, docked inspector, inline editing approach, and palette choices are all correct for an operational IDE. There are no blocking anti-patterns. The notes below are improvements and clarifications, not blockers.

---

## 1. Theme Colors

### Assessment: APPROVED with minor refinements

The proposed palette is well-matched to a local workflow IDE. The decisions are architecturally correct:

- **Graphite base** (`#101216` / `#0B0D11`) — correct. Low-stimulus background lets graph content carry attention. Does not compete with node/edge colors.
- **Violet accent** (`#8B5CF6`) — correct use as brand identity and selection indicator. The plan explicitly limits it to "selected authored objects and primary actions", which prevents the one-note problem.
- **Cyan runtime** (`#22D3EE`) — semantically distinct from violet. This is important: users must instantly read "selected by me" (violet) vs "running now" (cyan). Good separation.
- **Green / yellow / red for states** — industry-standard for FSM state visualization. Correct.

### Specific improvements

| Issue | Recommendation |
|---|---|
| `green: #22C55E` is saturated at full brightness | In dark mode, reduce to ~70% luminance (`#16A34A` or similar) for completed states so they don't visually "shout". Active/running states should be louder than done states. |
| `yellow: #F59E0B` on dark backgrounds | Check contrast against `bgSurface0 #1A1F27`. At small sizes (warning badge on node), amber-on-dark can fail 4.5:1. Consider `#FCD34D` for badge text on dark surface. |
| `textMuted: #687588` on `bgBase #101216` | Contrast ratio ~3.2:1 — passes for large text but fails for small labels. Reserve muted for truly inactive decorative text only. Use `textSecondary #AAB6C5` for any interactive or informational text. |
| Light theme `bgSurface0: #E3E8F0` + `textSecondary #455468` | Verify contrast — borderline at ~4.1:1. Bump textSecondary to `#394559` for light theme. |

### Color roles summary (keep these rules in code review)

```
violet  → I selected this / Pathly brand / primary CTA
cyan    → system is running this right now
blue    → active edge / current graph position
green   → this step is done
yellow  → needs attention (warning, waiting for review)
red     → blocked, error, destructive action
neutral → everything at rest
```

---

## 2. Ease of Use — 3-Pane Layout

### Assessment: CORRECT layout for this tool type

The library → canvas → inspector triad is the established pattern for node-graph editors (Blender, ComfyUI, n8n, Retool workflow builder). Experienced users will orient immediately. For new users:

**What works:**
- Left library as drag source is natural — users scan, grab, drop.
- Center canvas as primary workspace is correct. The graph IS the product.
- Right inspector as context panel is better than modals for a tool where users make many small edits.

**What needs attention:**

| Issue | Recommendation |
|---|---|
| Inspector panel has no visible "nothing selected" affordance described | The plan mentions a one-line hint ("Select a node or edge to edit."). This is correct — do NOT add card chrome or illustrations here. One muted line. |
| Library sections collapse by default for "advanced" areas but the plan doesn't specify which are advanced | Define this before Conversation 2. Suggested default-open: Flows, Skills, Agents. Default-collapsed: Templates, Workspace. |
| No keyboard shortcut surface mentioned | For an IDE audience: `N` to add node, `E` to connect (or drag from handle), `Delete`/`Backspace` to remove selected, `Ctrl+Z` undo. These don't need to be in Phase 1 but should be planned. Add a tooltip or command palette hint. |
| The "Add state" button (`+`) on the canvas toolbar is mentioned in the empty state hint but not in the component specs | Confirm this button exists in Phase 1 or Phase 7. If a user has no skills/agents to drag, they should still be able to add a bare state node. |

---

## 3. Configuration Flow — Node Inspector (THE KEY QUESTION)

### The flow, explained clearly

This is how it works, step by step:

```
1. User clicks "+ add state" or drags a skill/agent from the library onto the canvas
   → A node appears on the canvas (a circle/box representing one state in the FSM)

2. User clicks the node
   → The RIGHT PANEL (docked inspector) opens — NOT a modal
   → The canvas stays fully visible and interactive

3. Inspector shows 5 sections:
   ┌──────────────────────────┐
   │ Identity                 │  State ID (read-only, rename via YAML)
   │ Assigned behavior        │  Which skill/agent runs here (chip → popover picker)
   │ Required artifacts       │  Inputs/outputs this state expects
   │ Outgoing transitions     │  Summary of edges leaving this node
   │ Validation               │  Inline errors for this node
   └──────────────────────────┘

4. User edits fields inline (no save button needed — changes write to graph model immediately)

5. Validation runs continuously — issues show as inline red text below the field
   + a small warning badge appears on the node itself in the canvas
```

### Assessment: CORRECT. No modals needed for normal editing.

The docked panel is the right choice here. Modals would be wrong because:
- Users need to see the canvas context while editing (which state am I configuring? where does it connect?)
- Editing is iterative and fast — modals add friction per edit

**The one exception the plan correctly identifies:** Use a modal ONLY for:
1. Export confirmation when warnings exist (requires explicit acknowledgement)
2. Destructive confirms

### What to clarify before implementation

| Question | Answer from plan |
|---|---|
| Can the user rename a state ID? | NO — out of scope. Inspector shows ID as read-only with hint "Rename in YAML view for now." Correct decision. |
| What if the assigned behavior file is deleted from disk? | Shows warning badge + red text in inspector. The state remains selectable. Correct. |
| What if Required Artifacts section is empty? | Show muted "(none)" text — not an error. |
| Does editing the inspector auto-save? | No explicit save button. Changes write to graph model and mark the flow as "dirty" (unsaved dot in tab). User saves with Ctrl+S or the save button. Correct. |

---

## 4. Edge / Transition Configuration

### Assessment: COMPLEX — needs human-readable labels, not YAML key names

The underlying YAML structure for transition rules is:

```yaml
transition_rules:
  SOURCE_STATE:
    on_artifact:
      ARTIFACT.md: TARGET_STATE      # "when artifact arrives"
    on_content:
      - file: NOTES.md
        contains: "ready"
        next: TARGET_STATE           # "when file contains text"
    decide:
      question: "Where next?"
      options:
        approve: TARGET_STATE        # "human decision"
      default: approve
    default: TARGET_STATE            # "always go here"
```

**The UX risk:** Exposing `on_artifact`, `on_content`, `decide`, `default` as labels will confuse non-YAML users.

### Recommended inspector label mapping

| YAML key | Inspector label | Icon suggestion |
|---|---|---|
| `default` | "Always continues to →" | `ArrowRight` |
| `on_artifact` | "When artifact arrives:" | `FileCheck` |
| `on_content` | "When file contains:" | `FileSearch` |
| `decide` | "Human decision required:" | `GitFork` or `HelpCircle` |
| `transition_actions` | "Run before transitioning:" | `Zap` |

**This mapping should be in the EdgePanel component.** Do not show raw YAML keys in the inspector UI — they belong only in the YAML tab.

### Interaction notes

- **Adding a condition:** Small `+ Add condition` button at the bottom of the conditions section. Opens an inline form (type selector → fields for that type). NOT a modal.
- **Removing a condition:** `×` icon on the condition row, with a brief undo toast.
- **Multiple conditions to the same target:** Valid — show them stacked. Add a note if they could conflict (validation issue).

---

## 5. YAML Export Flow

### Assessment: SOLID — one clarification needed

The plan correctly:
- Disables Export until validation passes
- Shows warnings with explicit acknowledgement modal
- Uses one canonical YAML for all targets (Pathly package, Claude Code, Codex)
- Shows a toast with copy-path action on success

**The YAML IS the Python FSM definition.** To be explicit:

```
Visual graph (canvas) 
  ↓ serialized to
Canonical YAML (jsYaml.dump)
  ↓ written to
Pathly package path  → used by Python runtime (the FSM engine reads this YAML)
Claude Code path     → .claude/pathly-flows/
Codex path           → .codex/pathly-flows/
```

So yes — the exported YAML IS the Python FSM. The Python runtime reads `states`, `transitions`, `agent_map`, and `transition_rules` directly from this file. The visual editor is just a friendlier way to write that YAML.

### One UX improvement for export

The plan has a "target dropdown + Export button" in the canvas toolbar. Consider showing the last-exported path as a small muted line below the export area:

```
[Pathly package ▾]  [Export]
Last: src/pathly_data/core/flows/debug.flow.yaml  ✓ 3m ago
```

This gives users confidence the file is where they expect it.

---

## 6. Empty State and Onboarding

### Current hint: "Drag a skill or agent from the library, or click + to add a state."

### Assessment: SUFFICIENT for the target audience, but add one detail

This is correct for an IDE audience. Do NOT add:
- Illustrations or hero images
- "Get started" wizard re-entry
- Video tutorial links

**Do add:**
- A keyboard shortcut hint: `"...or press N to add a state"`
- If the library itself is empty (no skills/agents installed), show a second hint inside the library panel: `"No skills found. Run pathly install or drop .md files into skills/."`

### Empty inspector (nothing selected)

Plan says: one-line hint "Select a node or edge to edit."
Assessment: correct. Keep it muted, no chrome, no card.

---

## 7. UX Anti-Patterns and Red Flags

### No blockers. The following are items to watch during implementation:

| Risk | Detail | Mitigation |
|---|---|---|
| **Inspector z-index leak** | The plan has a z-index scale (canvas=0, inspector=10, popover=40, toast=60, modal=100). If this scale isn't enforced in code, behavior picker popover (z=40) will clip under toasts (z=60). | Create a single `zIndex.ts` constants file and import from there. |
| **React Flow handle discoverability** | Handles (the dots you drag to create edges) are invisible until hover. New users won't know to drag from them. | On node hover, show handles with a subtle animation (scale 0.8→1.0, 150ms). Consider a one-time tooltip on the first node: "Drag from dot to connect →" |
| **Behavior picker popover keyboard trap** | The plan correctly specifies up/down + Enter + Esc. If keyboard trap isn't implemented, keyboard-only users can't use the picker. | This is a Conversation 3 implementation detail — flag it in the Phase 9 spec. |
| **Dirty state tracking race** | If the user edits the inspector and immediately presses Ctrl+S, the save might capture a stale model if onChange is debounced. | Make onChange synchronous (no debounce) for inspector field edits. Debounce only for CodeMirror YAML edits. |
| **"No YAML comments" data loss** | YAML comments added by hand in the YAML tab will be silently dropped when the round-trip goes through the object model. | The plan notes this as a known edge case in Story S6. Add a one-time warning the first time a user edits YAML directly: "Comments in YAML are not preserved when switching to Visual view." |
| **Export button placement** | The export controls are in the canvas toolbar (top-right). If the canvas toolbar is already crowded with zoom/fit/lock controls, the Export button may be visually buried. | Keep Export visually separated — a small divider between layout controls (zoom/fit/lock) and authoring controls (validate/export). |
| **State ID generation collisions** | Phase 7 generates state IDs from skill names (e.g. `commit.md → COMMIT`, with `_2` suffix on collision). If a user drops 3 commits, they get `COMMIT`, `COMMIT_2`, `COMMIT_3` — correct but ugly. | This is acceptable for now. The note in the plan is sufficient. |

---

## Summary Scorecard

| Area | Score | Notes |
|---|---|---|
| Color palette | ✅ Strong | Minor contrast fixes for muted text and warning badges |
| Layout | ✅ Correct | 3-pane IDE pattern, well-reasoned |
| Node config flow | ✅ Correct | Docked inspector is right. No modals for normal edits. |
| Edge config UX | ⚠️ Needs label mapping | Use human-readable labels, not YAML key names, in inspector |
| YAML export | ✅ Solid | One canonical model, correct disable/warn/confirm pattern |
| Empty state | ✅ Sufficient | Add keyboard shortcut hint |
| Anti-patterns | ✅ None blocking | 7 items to watch during implementation |

**Overall: Implement as planned. Address the edge inspector label mapping (item 4) in Phase 10 and the z-index constants file early in Conversation 3.**
