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
- [ ] System prompt includes current FSM stage (read from `/next_action` on port 8765)
- [ ] System prompt includes active feature name (read from most-recently-modified `plans/*/FEATURE_INDEX.md`)
- [ ] System prompt includes matched skill name and description (passed from renderer)
- [ ] System prompt stays under 1,000 tokens (explainer context is smaller than general chat)

**Delivered by:** Conv 1

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

## Story S3.2: Run writes the skill command to the active terminal tab

**As a** Pathly Studio user, **I want** clicking Run to write the matched skill command to the
terminal tab (Claude Code or Codex), **so that** I don't have to copy-paste anything.

**Acceptance Criteria:**
- [ ] Clicking Run sends `{ command: "/pathly <skill>", target: "claude-code" | "codex" }` to IPC handler `chat:write-terminal`
- [ ] IPC handler writes `command + "\n"` to the active PTY for the specified tab
- [ ] MatchCard dims to "✓ Sent" state after Run
- [ ] If no terminal tab is open: IPC returns error, ChatPanel shows inline toast "Open a terminal tab first"
- [ ] OutputSnippet appears below MatchCard showing live PTY output lines

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
