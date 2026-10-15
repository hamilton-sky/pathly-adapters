// One local-model call at a time. The built-in runtime streams every answer on the
// same untagged llm:token / llm:done events, so two calls in flight would read each
// other's text (an HQ answer swallowing a dropped artifact's summary, or the reverse)
// — and each holds its own multi-GB context. Every built-in call (HQ chat, the
// operator turn, artifact summaries) goes through runLocal, FIFO.
//
// Owners: 'chat' is HQ's answer — Stop ends it (llm:abort while it runs, or drops it
// while it waits). 'background' (summaries) is never stopped by HQ's Stop.

export type LocalOwner = 'chat' | 'background'

let tail: Promise<unknown> = Promise.resolve()
let running: LocalOwner | null = null
const waitingChat = new Set<() => void>()

/** Queue *fn*; it starts when every earlier call has finished. A queued chat call
 *  that Stop drops resolves with *dropped* without ever reaching the model. */
export function runLocal<T>(owner: LocalOwner, fn: () => Promise<T>, dropped: T): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    let skip = false
    const drop = (): void => { skip = true; resolve(dropped) }
    if (owner === 'chat') waitingChat.add(drop)
    tail = tail.then(async () => {
      waitingChat.delete(drop)
      if (skip) return
      running = owner
      try {
        resolve(await fn())
      } catch (err) {
        reject(err)
      } finally {
        running = null
      }
    })
  })
}

/** HQ's Stop: end the chat answer — the running one, or one still waiting. */
export function stopChat(abortRunning: () => void): void {
  for (const drop of [...waitingChat]) drop()
  waitingChat.clear()
  if (running === 'chat') abortRunning()
}

/** Test seam: what is running now. */
export function runningOwner(): LocalOwner | null {
  return running
}
