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
//   • FOLDER TRUST — claude asks once per never-before-seen directory ("Do you trust the
//     files in this folder?") and records the answer in ~/.claude.json. It is NOT the same
//     screen as the bypass-permissions warning and is NOT waived by
//     --dangerously-skip-permissions, so every first run in a fresh project hit it.
//   • BYPASS PERMISSIONS — the --dangerously-skip-permissions confirmation.
//
// Answering these automatically is the intended behavior here: Pathly is a headless
// orchestrator (no human in the per-step loop), the run already carries an explicit
// autonomy flag, and cwd is validated under $HOME before spawn. We log every auto-answer
// so it stays auditable rather than silent.
const TRUST_PROMPT_RE = /Do you trust the files in this (?:folder|directory)|trust the files in|folder is not trusted/i
const BYPASS_PROMPT_RE = /Bypass Permissions mode/i

/** Watch a HEADLESS engine PTY for a startup gate and answer it, so a first-run trust
 *  prompt fails-open into a real run instead of hanging the stage forever. Interactive
 *  tabs handle their own gates inline (they must also inject a prompt afterwards). */
function attachHeadlessGateDismisser(p: import('node-pty').IPty, tabId: string): void {
  let buf = ''
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
    if (!trustDone && TRUST_PROMPT_RE.test(buf)) {
      trustDone = true
      slog('gate', tabId, 'auto-answered folder-trust prompt')
      p.write('\r')
      buf = ''
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
  //   Phase 1 — if the --dangerously-skip-permissions warning screen appears,
  //             auto-dismiss it with a bare \r and keep watching.
  //
  //   Phase 2 — wait for Claude's '> ' input prompt (ANSI-stripped), which is the
  //             reliable signal that readline is ready to accept input.
  //             Then send bracketed paste + \r as ONE atomic write.
  //             Splitting into two writes with a delay is racy — \r can arrive while
  //             Claude is still flushing startup output, confusing readline.
  //             (This is the same lesson learned in launchTerminal.ts writeToTerminal.)
  //
  //   Fallback — if '> ' never appears within 5 s, inject anyway.
  if (initialInput) {
    let injected = false
    let bypassDismissed = false
    let trustDismissed = false
    let strippedBuf = ''

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

    const fallbackTimer = setTimeout(doInject, 5000)

    const unsubscribe = ptyProcess.onData((data: string) => {
      if (injected) return
      // Strip ANSI escape sequences so pattern matching works reliably
      strippedBuf += stripAnsi(data)

      // Phase 1: auto-dismiss either startup gate. Both are cleared the same way (Enter
      // accepts the default). Reset the buffer after answering — the dismissed screen's
      // own text can contain "> ", which would otherwise read as "readline is ready" in
      // phase 2 and inject the prompt into a UI that isn't listening yet.
      if (!bypassDismissed && BYPASS_PROMPT_RE.test(strippedBuf)) {
        bypassDismissed = true
        slog('gate', tabId, 'auto-answered bypass-permissions screen')
        ptyProcess.write('\r')
        strippedBuf = ''
        return
      }
      if (!trustDismissed && TRUST_PROMPT_RE.test(strippedBuf)) {
        trustDismissed = true
        slog('gate', tabId, 'auto-answered folder-trust prompt')
        ptyProcess.write('\r')
        strippedBuf = ''
        return
      }

      // Phase 2: Claude's '> ' prompt means readline is ready — inject now
      if (strippedBuf.includes('> ')) {
        doInject()
      }
    })
  } else if (headlessEngine) {
    // A headless one-shot has no injector, so before this it had NO path at all for a
    // startup gate — a first run in an untrusted folder simply hung until killed.
    attachHeadlessGateDismisser(ptyProcess, tabId)
  }
}
