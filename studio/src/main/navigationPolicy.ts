// What an app window may do when its page tries to go somewhere else.
//
// App windows load the renderer WITH the preload, so whatever page they show gets
// window.pathly (terminal spawn, fs). Rendered board/agent/model text can carry links;
// a click that navigated the window itself to a remote page would hand that page the
// whole bridge. So only the app's own origin may load in-window; http(s)/mailto open in
// the system browser; anything else (javascript:, data:, file: from a remote page, …) is
// dropped. Pure so it can be unit-tested without Electron (see windowSecurity.ts).

export type NavigationDecision = 'allow' | 'external' | 'block'

const EXTERNAL_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

function parse(url: string): URL | null {
  try {
    return new URL(url)
  } catch {
    return null
  }
}

/** Is `target` the app itself (same dev-server origin, or the packaged file:// bundle)? */
function isAppUrl(current: URL, target: URL): boolean {
  if (current.protocol === 'file:') return target.protocol === 'file:'
  return target.origin !== 'null' && target.origin === current.origin
}

/** A main-frame navigation from `currentUrl` (the app page) to `targetUrl`. */
export function navigationDecision(currentUrl: string, targetUrl: string): NavigationDecision {
  const target = parse(targetUrl)
  if (!target) return 'block'
  const current = parse(currentUrl)
  if (current && isAppUrl(current, target)) return 'allow'
  return EXTERNAL_PROTOCOLS.has(target.protocol) ? 'external' : 'block'
}

/** window.open / target=_blank: never a new app window; safe schemes go to the browser. */
export function windowOpenDecision(targetUrl: string): Exclude<NavigationDecision, 'allow'> {
  const target = parse(targetUrl)
  return target && EXTERNAL_PROTOCOLS.has(target.protocol) ? 'external' : 'block'
}
