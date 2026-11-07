// Startup handling for a freshly spawned engine PTY: answer the CLI's blocking startup
// gates, and — for an interactive tab — inject the initial prompt once readline is ready.
//
// This is a state machine over raw PTY bytes, which is why it lives alone: it is the only
// part of the spawn path that has to reason about terminal rendering rather than process
// lifecycle, and it must never be entangled with the retry/telemetry logic around it.

import { slog } from './log'

/** Strip ANSI so pattern matching works on the rendered text, not the escape soup. */
function stripAnsi(s: string): string {
  return s
    .replace(/\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]/g, '')
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
}

// Interactive gates an engine can raise at startup. Each one BLOCKS the process until
// answered — which is fatal for a headless one-shot: the PTY never exits, no result is
// ever POSTed, and the stage hangs instead of failing. Two distinct screens:
//
//   • FOLDER TRUST — claude asks once per never-before-seen directory and records the
//     answer in ~/.claude.json. It is NOT the same screen as the bypass-permissions warning
//     and is NOT waived by --dangerously-skip-permissions. Two wordings are matched: the old
//     "Do you trust the files in this folder?" and the current "Is this a project you created
//     or one you trust? … Yes, I trust this folder" (__tests__/claude-trust-screen.txt, with
//     its source). The current screen draws its words with cursor-column moves, so the
//     ANSI-stripped text has no spaces: the phrases match with \s*. It puts the cursor on
//     "No, exit" (Enter alone exits claude), so the answer is Down then Enter whenever the
//     cursor sits on "No, exit", else Enter. It also ignores keys for its first ~0.2 s, so the
//     answer is written TRUST_ANSWER_DELAY_MS after the screen is seen.
//   • BYPASS PERMISSIONS — the --dangerously-skip-permissions confirmation.
//
// Answering these automatically is the intended behavior here: Pathly is a headless
// orchestrator (no human in the per-step loop), the run already carries an explicit
// autonomy flag, and cwd is validated under $HOME before spawn. We log every auto-answer
// so it stays auditable rather than silent.
const TRUST_PROMPT_RE = /Do you trust the files in this (?:folder|directory)|trust the files in|folder is not trusted|Is\s*this\s*a\s*project\s*you\s*created\s*or\s*one\s*you\s*trust|Yes,\s*I\s*trust\s*this\s*folder/i
const BYPASS_PROMPT_RE = /Bypass Permissions mode/i
const TRUST_OPTION_RE = /trust\s*this\s*folder|No,\s*exit/i
const TRUST_SCREEN_TEXT_RE = /[\s\S]*(?:trust\s*this\s*folder|No,\s*exit)/i
const CURSOR_ON_NO_RE = /\u276f\s*(?:\d+\.\s*)?No,\s*exit/i
const TRUST_ANSWER_DELAY_MS = 1000

// claude's ready prompt: "> " (older builds) or "❯" + a no-break space (measured, current).
// The trust screen's own "❯No, exit" / "❯ 1. Yes" never reach this check: the buffer is
// reset after the answer and any re-drawn screen text is cut off first.
const READY_PROMPT_RE = /> |\u276f[\u00a0 ](?!\s*\d+\.)/

// A chief tab (`open_chief` sends tab_id = the run id) is pasted into only on the ready
// prompt, never on the blind fallback: a paste that lands in a startup screen is lost.
const CHIEF_TAB_RE = /^chief-[0-9a-f]{12}$/

/** The keys that accept the trust screen in `buf`. */
function trustAnswerKeys(buf: string): string {
  return CURSOR_ON_NO_RE.test(buf) ? '\x1b[B\r' : '\r'
}

/** Watch a HEADLESS engine PTY for a startup gate and answer it, so a first-run trust
 *  prompt fails-open into a real run instead of hanging the stage forever. Interactive
 *  tabs handle their own gates inline (they must also inject a prompt afterwards). */
function attachHeadlessGateDismisser(p: import('node-pty').IPty, tabId: string): void {
  let buf = ''
  let trustSeen = false
  let trustDone = false
  let bypassDone = false
  const sub = p.onData((chunk: string) => {
    if (trustDone && bypassDone) { sub.dispose(); return }
    buf = (buf + stripAnsi(chunk)).slice(-4000)
    if (!bypassDone && BYPASS_PROMPT_RE.test(buf)) {
      bypassDone = true
      slog('gate', tabId, 'auto-answered bypass-permissions screen')
      p.write('\r')
      buf = ''
      return
    }
    if (!trustSeen && TRUST_PROMPT_RE.test(buf)) {
      trustSeen = true
      setTimeout(() => {
        trustDone = true
        slog('gate', tabId, 'auto-answered folder-trust prompt')
        p.write(trustAnswerKeys(buf))
        buf = ''
      }, TRUST_ANSWER_DELAY_MS)
    }
  })
  // Startup gates only appear in the first seconds; stop watching so a long run's output
  // can never trip these patterns mid-flight (e.g. an agent echoing the prompt text).
  setTimeout(() => sub.dispose(), 30000)
}

/**
 * Attach whatever startup handling this PTY needs.
 *
 * An INTERACTIVE tab (`initialInput` present) runs the two-phase injector below and answers
 * its own gates inline, because it must dismiss them and then type. A HEADLESS one-shot has
 * no injector, so it gets the standalone dismisser — without it a first run in an untrusted
 * folder simply hung until killed.
 */
export function attachStartupHandling(
  ptyProcess: import('node-pty').IPty,
  opts: { tabId: string; initialInput?: string; headlessEngine: boolean },
): void {
  const { tabId, initialInput, headlessEngine } = opts
  // Inject the stage prompt using the same two-phase pattern as launchTerminal.ts:
  //
  //   Phase 1 — answer a startup gate (bypass-permissions screen, folder-trust screen)
  //             and keep watching.
  //
  //   Phase 2 — wait for Claude's ready prompt (READY_PROMPT_RE, ANSI-stripped), which is
  //             the reliable signal that readline is ready to accept input.
  //             Then send bracketed paste + \r as ONE atomic write.
  //             Splitting into two writes with a delay is racy — \r can arrive while
  //             Claude is still flushing startup output, confusing readline.
  //             (This is the same lesson learned in launchTerminal.ts writeToTerminal.)
  //
  //   Fallback — if the ready prompt never appears within 5 s, inject anyway; except in a
  //             chief tab, which only logs and keeps waiting (CHIEF_TAB_RE).
  if (initialInput) {
    const chiefTab = CHIEF_TAB_RE.test(tabId)
    let injected = false
    let bypassDismissed = false
    let trustSeen = false
    let trustDismissed = false
    let strippedBuf = ''
    let fallbackTimer: ReturnType<typeof setTimeout> | undefined

    const doInject = (): void => {
      if (injected) return
      injected = true
      clearTimeout(fallbackTimer)
      unsubscribe.dispose()
      // Write the bracketed paste.
      ptyProcess.write('\x1b[200~' + initialInput + '\x1b[201~')
      // Wait for Claude to render the paste indicator '[Pasted text…]' in the
      // terminal output — that confirms Ink has finished processing the paste
      // and the input field is active. Then send \r to submit.
      // Same event-driven approach as waiting for '> ' before injecting.
      // Fallback: send \r after 6 s if the indicator never appears (large prompts
      // can take several seconds to render in Claude's Ink UI).
      let enterSent = false
      const enterFallback = setTimeout(() => {
        if (!enterSent) { enterSent = true; ptyProcess.write('\r') }
      }, 6000)
      let pasteBuf = ''
      const pasteRenderSub = ptyProcess.onData((chunk: string) => {
        if (enterSent) return
        pasteBuf += chunk
          .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
          .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, '')
        // Claude shows "[Pasted text", "[Large input", or "[Input (N lines)]"
        // depending on prompt size — match any of these paste-complete signals.
        if (/\[Pasted text|\[Large input|\[Input \(/.test(pasteBuf)) {
          enterSent = true
          clearTimeout(enterFallback)
          pasteRenderSub.dispose()
          ptyProcess.write('\r')
        }
      })
    }

    fallbackTimer = setTimeout(() => {
      if (chiefTab) {
        slog('gate', tabId, 'no ready prompt yet: chief tab waits for it (no blind paste)')
        return
      }
      slog('gate', tabId, 'no ready prompt yet: pasting on the 5 s fallback')
      doInject()
    }, 5000)

    const unsubscribe = ptyProcess.onData((data: string) => {
      if (injected) return
      // Strip ANSI escape sequences so pattern matching works reliably
      strippedBuf += stripAnsi(data)

      // Phase 1: auto-dismiss either startup gate (Enter, or Down then Enter when the trust
      // screen's cursor sits on "No, exit"). Reset the buffer after answering — the dismissed screen's
      // own text can contain "> ", which would otherwise read as "readline is ready" in
      // phase 2 and inject the prompt into a UI that isn't listening yet.
      if (!bypassDismissed && BYPASS_PROMPT_RE.test(strippedBuf)) {
        bypassDismissed = true
        slog('gate', tabId, 'auto-answered bypass-permissions screen')
        ptyProcess.write('\r')
        strippedBuf = ''
        return
      }
      if (!trustSeen && TRUST_PROMPT_RE.test(strippedBuf)) {
        trustSeen = true
        setTimeout(() => {
          if (injected) return
          trustDismissed = true
          slog('gate', tabId, 'auto-answered folder-trust prompt')
          ptyProcess.write(trustAnswerKeys(strippedBuf))
          strippedBuf = ''
        }, TRUST_ANSWER_DELAY_MS)
      }
      // Never read the trust screen as the ready prompt: wait while it is up, and after
      // the answer cut off any re-drawn screen text (it shows "❯Yes, I trust this folder").
      if (trustSeen && !trustDismissed) return
      if (trustDismissed && TRUST_OPTION_RE.test(strippedBuf)) {
        strippedBuf = strippedBuf.replace(TRUST_SCREEN_TEXT_RE, '')
      }

      // Phase 2: Claude's ready prompt means readline is ready — inject now
      if (READY_PROMPT_RE.test(strippedBuf)) {
        doInject()
      }
    })
  } else if (headlessEngine) {
    // A headless one-shot has no injector, so before this it had NO path at all for a
    // startup gate — a first run in an untrusted folder simply hung until killed.
    attachHeadlessGateDismisser(ptyProcess, tabId)
  }
}
