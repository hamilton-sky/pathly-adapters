# Studio AI Chat — User Stories

## Context

Pathly Studio is an Electron desktop app that orchestrates a development pipeline via an FSM server.
Users run Pathly skills (`/pathly build`, `/pathly review`, etc.) through Claude Code or Codex CLIs
in embedded terminal tabs. This feature adds a **Conductor** chat panel — a right-side sidebar that
interprets plain-English intent, matches it to the right Pathly skill via embedding similarity, and
writes the matched command to the appropriate terminal with user approval.

The user never needs to remember skill names or CLI syntax.

---

## Story S1.1: Chat server responds to explanations via phi4-mini

**As a** Pathly Studio user, **I want** to receive a natural-language explanation of why a skill
was matched to my intent, **so that** I understand what will happen before I click Run.

**Acceptance Criteria:**
- [ ] `POST /chat` endpoint exists on the Pathly Python server (port 8765)
- [ ] Request body: `{ "message": string, "matchedSkill": string, "skillDescription": string, "history": Message[], "context": PathlyContext }`
- [ ] Response streams text back via SSE (`text/event-stream`)
- [ ] phi4-mini system prompt is set to "explainer" role — does NOT choose or suggest skills
- [ ] phi4-mini explanation is 2–3 sentences max, references FSM stage and feature name
- [ ] If Ollama is not running, explanation area shows "Ollama offline — explanation unavailable" (match card still appears)

**Delivered by:** Conv 1

---

## Story S1.2: System prompt includes active Pathly context

**As a** Pathly Studio user, **I want** the explanation to reference my current pipeline stage
and feature, **so that** it's specific to what I'm doing right now.

**Acceptance Criteria:**
- [ ] System prompt includes current FSM stage (read from `/status` on port 8765 via `read_state()` — **not** `/next_action`, which writes to disk)
- [ ] System prompt includes active feature name (read from most-recently-modified `plans/*/FEATURE_INDEX.md`)
- [ ] System prompt includes matched skill name and description (passed from renderer)
- [ ] System prompt stays under 1,000 tokens (explainer context is smaller than general chat)

**Delivered by:** Conv 1

---

## Story S2.4: Empty state guides user to start a new flow

**As a** Pathly Studio user opening the Conductor with no active feature (or for the first time),
**I want** to see a clear starting point, **so that** I can create a new development flow without
knowing any Pathly skill names.

**Acceptance Criteria:**
- [ ] When `messages.length === 0` and no active feature (`fsmStage === "unknown"`): show "What do you want to build?" prompt with quick-start chips `[▸ po]` `[▸ plan]` `[▸ storm]`
- [ ] When `messages.length === 0` and a feature IS active: show feature name + current FSM stage + "Describe what you want to do next"
- [ ] Clicking a quick-start chip (`po`, `plan`, `storm`) immediately sets `currentMatch` to that skill — bypasses embedding — and fires phi4-mini explanation
- [ ] Empty state disappears as soon as the first message is sent
- [ ] User can describe "I want to build a login page" → Conductor routes to `/pathly po` and starts the flow from scratch

**Delivered by:** Conv 2

---

## Story S2.1: Collapsible Conductor panel in Studio

**As a** Pathly Studio user, **I want** the Conductor panel on the right side of Studio that I
can open and close, **so that** it doesn't take up space when I don't need it.

**Acceptance Criteria:**
- [ ] ChatPanel renders as a right-side flex child in Studio's body layout (300px wide)
- [ ] Panel has a `[›]` collapse button that hides the panel (36px strip with toggle icon)
- [ ] Panel open/closed state persists in Zustand `uiStore.chatOpen`
- [ ] ConductorHeader shows `⚡ Conductor` title + `[Manual]`/`[Auto]` toggle + CLI pills
- [ ] Claude Code pill: blue `#38BDF8`, Codex pill: amber `#F59E0B`
- [ ] Active CLI pill has colored dot + colored border; idle pill is 45% opacity with grey dot

**Delivered by:** Conv 2

---

## Story S2.2: Messages stream in real-time

**As a** Pathly Studio user, **I want** the phi4-mini explanation to stream word by word,
**so that** the interaction feels responsive.

**Acceptance Criteria:**
- [ ] User message appears immediately on send
- [ ] phi4-mini explanation streams character-by-character
- [ ] Blinking cursor shows while streaming is in progress
- [ ] Stop button (red ■) in ChatInput replaces Send during streaming
- [ ] Streaming can be cancelled; partial explanation is kept with `[stopped]` marker

**Delivered by:** Conv 2

---

## Story S2.3: Skills panel shows all available Pathly skills as chips

**As a** Pathly Studio user, **I want** to see all available Pathly skills as clickable chips
in the panel, **so that** I can pick one directly without typing.

**Acceptance Criteria:**
- [ ] SkillsPanel renders below ConductorHeader with all skills from skills.json
- [ ] Each chip shows the skill name (e.g. `build`, `review`, `test`)
- [ ] Clicking a chip bypasses embedding and directly creates a MatchCard for that skill
- [ ] The matched skill's chip highlights (accent border + accent text) when a match is found
- [ ] SkillsPanel is collapsible; state persists in `uiStore.skillsPanelOpen`

**Delivered by:** Conv 2

---

## Story S3.1: MatchCard shows matched skill with confidence score

**As a** Pathly Studio user, **I want** to see which skill was matched and how confident the
system is, **so that** I can make an informed decision before running.

**Acceptance Criteria:**
- [ ] MatchCard appears in the message list after intent is submitted
- [ ] Card shows: match status label, confidence bar (0–100%), skill name (large, monospace), skill description, command preview (`$ /pathly <skill>`), alternative matches with scores, Run and "Not this" buttons
- [ ] High confidence (≥65%): green border-left, green bar, `✓ MATCHED` label
- [ ] Low confidence (<65%): amber border-left, amber bar, `~ UNSURE` label, alternatives more prominent
- [ ] No match (<40%): text message "I couldn't match this — try rephrasing or pick a skill above"
- [ ] Clicking an alternative chip re-renders the MatchCard for that skill

**Delivered by:** Conv 3

---

## Story S3.2: Run writes the correct host command to the active terminal tab

**As a** Pathly Studio user, **I want** clicking Run to write the skill command to the correct
terminal tab in the format that tab understands, **so that** I don't have to copy-paste anything
or know CLI syntax differences.

**Acceptance Criteria:**
- [ ] Renderer looks up active tab from `terminalStore.tabs` by `kind` ('claude' or 'codex')
- [ ] If no tab of the target kind exists: renderer calls `launchTerminal(kind, cwd)` to auto-spawn one, then writes
- [ ] Command is generated in the **host-correct format**:
  - Claude Code tab (`kind === 'claude'`): `/pathly <skill>` (e.g. `/pathly build`)
  - Codex tab (`kind === 'codex'`): `Use Pathly <skill>` (e.g. `Use Pathly build`)
- [ ] Renderer sanitizes command (strips `;`, `&&`, `||`, `|`, `>`, `<`) before writing
- [ ] Renderer calls `window.pathly.terminal.write(tabId, command + '\n')` directly — no new IPC channel
- [ ] MatchCard dims to "✓ Sent" state after Run
- [ ] OutputSnippet appears below MatchCard showing live PTY output lines (via `window.pathly.terminal.onData`)

**Delivered by:** Conv 3

---

## Story S4.1: Context includes current FSM stage and screen state

**As a** Pathly Studio user, **I want** the AI's explanation to reference what's on my screen
and what stage I'm in, **so that** the explanation is specific not generic.

**Acceptance Criteria:**
- [ ] `buildPathlyContext()` runs before each message send
- [ ] Returns `{ fsmStage, featureName, screenElements, skills }`
- [ ] Screen context capped at 500 tokens
- [ ] If FSM server unreachable, `fsmStage` defaults to `"unknown"`

**Delivered by:** Conv 4

---

## Story S4.2: Skills list is always available in context

**As a** Pathly Studio user, **I want** the AI to always know what skills exist,
**so that** its explanation references the correct skill name.

**Acceptance Criteria:**
- [ ] `KNOWN_SKILLS` list from `skills.json` is always included in the request context
- [ ] phi4-mini references skill names correctly (e.g. `/pathly build`, `/pathly review`)

**Delivered by:** Conv 4

---

## Story S5.1: MiniLM embedding model loads at startup

**As a** Pathly Studio user, **I want** the embedding router to be ready before I type my
first message, **so that** routing is instant when I need it.

**Acceptance Criteria:**
- [ ] `@xenova/transformers` loads `all-MiniLM-L6-v2` in the renderer at app startup (not on first use)
- [ ] While loading: MiniLM pill shows `◈ Loading…` (purple)
- [ ] After loading: pill shows `◈ MiniLM · ready`
- [ ] All skills from `skills.json` are pre-embedded and stored in memory at startup
- [ ] Total startup overhead < 3 seconds on first run (model cached on disk after first load)

**Delivered by:** Conv 5

---

## Story S5.2: Embedding similarity matches intent to Pathly skill

**As a** Pathly Studio user, **I want** to type what I want in plain English and get the right
Pathly skill suggested immediately, **so that** I never need to remember skill names.

**Acceptance Criteria:**
- [ ] On message send: `matchIntent(input)` runs cosine similarity against all skill vectors
- [ ] Top match + top 2 alternatives returned with scores
- [ ] MatchCard renders within 50ms of message send (before phi4-mini responds)
- [ ] Matched skill chip highlights in SkillsPanel
- [ ] Correct skill is matched for common phrasings:
  - "I want to build" → `/pathly build`
  - "check the code" → `/pathly review`
  - "something is broken" → `/pathly debug`
  - "write the plan" → `/pathly plan`
  - "run tests" → `/pathly test`

**Delivered by:** Conv 5

---

## Story S5.3: Low-confidence state guides user to correct skill

**As a** Pathly Studio user, **I want** the panel to tell me when it's not sure about a match,
**so that** I can correct it rather than running the wrong skill.

**Acceptance Criteria:**
- [ ] When top score < 65%: card is amber `~ UNSURE`, alternatives are visually prominent
- [ ] "Not this" button is clearly labelled (not "Dismiss")
- [ ] Clicking "Not this" clears the MatchCard and returns focus to input with placeholder "Try rephrasing…"
- [ ] Clicking an alternative skill chip replaces the current MatchCard with a new one for that skill

**Delivered by:** Conv 5

---

## Story S6.1: AI receives a static schema of Studio's key UI elements

**As a** Pathly Studio user, **I want** the AI to know what's in Studio without runtime scanning,
**so that** it can generate accurate automation steps based on a reliable, always-correct element map.

**Acceptance Criteria:**
- [ ] `getStudioSchema()` returns a typed list of elements, each with `screen`, `type`, `label`, `description`
- [ ] Schema is included in every POST /chat request as `studioSchema`
- [ ] AI references element labels (not IDs) when generating automation steps
- [ ] Schema covers FlowEditor, StepEditor, ChatPanel, and modal CTAs
- [ ] `studioSchema.ts` is a typed constant — no hooks, no subscriptions, no runtime scanning

**Delivered by:** Conv 6

---

## Story S6.2: AI system prompt includes Studio UI context

**As a** Pathly Studio user, **I want** the AI's system prompt to describe what Studio's interface looks like,
**so that** the AI generates steps that reference real, accessible element labels.

**Acceptance Criteria:**
- [ ] System prompt includes a `## Studio UI Elements` section listing elements grouped by screen
- [ ] AI-generated automation steps reference only labels from this list
- [ ] Schema contribution to system prompt is capped at 400 tokens

**Delivered by:** Conv 6

---

## Story S7.1: Playwright executor connects to Electron window

**As a** Pathly Studio user, **I want** the automation executor to be ready when Studio starts,
**so that** the first automation request can run without setup delay.

**Acceptance Criteria:**
- [ ] `PlaywrightExecutor.connect(cdpUrl)` establishes a CDP connection to the running Studio window
- [ ] Executed at app startup (after `app.ready`), available before first automation request
- [ ] CDP remote debugging port is set before `BrowserWindow` is created

**Delivered by:** Conv 7

---

## Story S7.2: AI can click, fill, or select any Studio element by label

**As a** Pathly Studio user, **I want** the AI to interact with Studio UI elements using their visible labels,
**so that** automation works without fragile DOM IDs or injected attributes.

**Acceptance Criteria:**
- [ ] `executeStep({ type: 'click', label: 'New Flow' })` finds and clicks the matching element
- [ ] Element resolution cascade: `getByRole` → `getByLabel` → `getByPlaceholder` → `getByText`
- [ ] If not found: returns `{ ok: false, error: 'element not found: New Flow' }` — no crash
- [ ] Disabled element check: returns `{ ok: false, error: 'element disabled: Save' }`
- [ ] Works for click, fill (React synthetic events), and selectOption

**Delivered by:** Conv 7

---

## Story S7.3: Step execution is reliable across UI changes

**As a** Pathly Studio user, **I want** automation steps to degrade gracefully if a label changes,
**so that** a renamed button gives a clear error instead of silently breaking the flow.

**Acceptance Criteria:**
- [ ] If an element label changes (e.g. "New Flow" → "Create Flow"), the `getByText` fallback tries a partial match
- [ ] If still not found: step returns a clear error with the label that wasn't found
- [ ] No silent failures — every failed step produces an actionable error message
- [ ] Fix path is simple: update the label in `studioSchema.ts`

**Delivered by:** Conv 7

---

## Story S8.1: Staged mode shows each AI action step and waits for approval

**As a** Pathly Studio user, **I want** the AI to show me each action it plans to take before executing it,
**so that** I stay in control and can catch mistakes.

**Acceptance Criteria:**
- [ ] After AI generates an action plan, `AutomationCard` appears showing the intent and step count
- [ ] `[Step by Step]` button activates staged mode
- [ ] `StepQueue` renders each step as a card with description and action preview
- [ ] Current step is highlighted with `[✓ Approve]` and `[→ Skip]` buttons
- [ ] Approve executes the action and advances to the next step
- [ ] Skip marks step as skipped and advances without executing
- [ ] Completed steps remain visible, dimmed, with `✓` or `→` badge

**Delivered by:** Conv 8

---

## Story S8.2: Auto mode executes the full action plan without interruption

**As a** Pathly Studio user, **I want** to hand off a full flow creation to the AI and have it complete everything automatically,
**so that** I can describe what I want once and walk away.

**Acceptance Criteria:**
- [ ] `[▶ Run All]` button activates auto mode
- [ ] All steps execute in sequence with 300ms delay between each
- [ ] Progress bar shows `n / total` steps completed
- [ ] `[■ Stop]` button halts execution at the current step
- [ ] After completion: AI sends a summary message listing what was created

**Delivered by:** Conv 8

---

## Story S8.3: Auto mode is blocked when confidence is low

**As a** Pathly Studio user, **I want** the AI to force step-by-step review when it's uncertain,
**so that** I don't end up with a wrong flow created automatically.

**Acceptance Criteria:**
- [ ] If AI confidence in the action plan is below threshold: `[▶ Run All]` button is disabled
- [ ] Tooltip on disabled Run All: "Confidence too low for auto mode — use Step by Step"
- [ ] Staged mode is always available regardless of confidence

**Delivered by:** Conv 8

---

## Story S8.4: User can create a complete flow from a plain-English description

**As a** Pathly Studio user, **I want** to describe what I want to build in plain English and have the AI create the flow in Studio for me,
**so that** I never have to manually navigate menus, fill forms, or remember step types.

**Acceptance Criteria:**
- [ ] User types "create a checkout flow with an HTTP step to Stripe and a condition step" → AI generates a complete action plan
- [ ] Action plan covers: create flow, name it, add each step, configure step type, fill required fields
- [ ] Staged or Auto mode executes the plan in Studio
- [ ] After completion: flow exists in Studio with the correct structure

**Delivered by:** Conv 8

---

## Story S9.1: User can see all available AI models with system requirements

**As a** Pathly Studio user, **I want** to see what local AI models are available and what hardware they need,
**so that** I can pick the right one for my device.

**Acceptance Criteria:**
- [ ] Model selector dropdown shows in the Conductor header (replaces the `phi4-mini` pill)
- [ ] Dropdown lists 4 models: Qwen2.5 Coder 7B, Qwen3 4B, Phi-4 Mini, Llama 3.2 3B
- [ ] Each model card shows: name, description, use case, SYSTEM / STORAGE / SPEED specs
- [ ] `Recommended` badge on Phi-4 Mini
- [ ] `Cached` badge on models already downloaded

**Delivered by:** Conv 9

---

## Story S9.2: User can download and cache a model with a toggle

**As a** Pathly Studio user, **I want** to download and cache a model with one click,
**so that** it loads instantly on future app starts.

**Acceptance Criteria:**
- [ ] Each model card has a `Cache` toggle
- [ ] Turning toggle on starts download — linear progress bar appears under the card
- [ ] After download: toggle shows green, `Cached` badge appears
- [ ] Turning toggle off deletes the cached model after confirmation
- [ ] Download progress persists if the panel is closed and reopened

**Delivered by:** Conv 9

---

## Story S9.3: Selected model is used for all AI responses in the Conductor

**As a** Pathly Studio user, **I want** the Conductor to use my chosen model for all explanations and action planning,
**so that** I get responses that match my device capability.

**Acceptance Criteria:**
- [ ] Changing model selection immediately uses the new model for the next message
- [ ] If selected model is not cached: Conductor shows "Download this model to use it" inline
- [ ] ChatInput model pill shows the short name of the currently selected model
- [ ] WebLLM streams responses the same way Ollama did — character by character in the message bubble

**Delivered by:** Conv 9

---

## Story S9.4: Model selection persists across app restarts

**As a** Pathly Studio user, **I want** my model choice to be remembered,
**so that** I don't have to re-select it every time I open Studio.

**Acceptance Criteria:**
- [ ] `modelStore.selectedModelId` persists via Zustand persist middleware
- [ ] On app start: selected model loads automatically if cached
- [ ] If selected model is no longer cached (user cleared storage): falls back to Phi-4 Mini (recommended default)

**Delivered by:** Conv 9
