import { Marked } from 'marked'

// Markdown → HTML for UNTRUSTED text: a local model's answer, board posts, artifact
// bodies, agent results, composed prompts. This renderer can reach window.pathly
// (terminal spawn), so injected HTML must never go live: raw HTML is escaped, links
// are limited to http(s)/mailto (they open in the system browser — main's
// windowSecurity.ts denies any in-app navigation), and images show as their alt text
// unless the caller opts in. `marked` alone sanitizes nothing; every Markdown sink in
// the renderer goes through here.

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ESCAPES[c])
}

const SAFE_HREF = /^(https?:|mailto:)/i
// Remote or inline raster images only — never svg (it can carry markup) or other schemes.
const SAFE_IMG_SRC = /^(https?:|data:image\/(png|jpe?g|gif|webp);base64,)/i

export interface SafeMarkdownOptions {
  /** Single newlines become <br> (chat style). Default true; `false` matches plain `marked()`. */
  breaks?: boolean
  /**
   * Render http(s) / inline raster images as <img>. Only for the user's own document
   * (an image can't run script, but it does fetch a remote URL). Default false: alt text.
   */
  images?: boolean
}

function buildRenderer(breaks: boolean, images: boolean): Marked {
  const md = new Marked({ gfm: true, breaks })
  md.use({
    renderer: {
      html({ text }) {
        return escapeHtml(text)
      },
      link({ href, title, tokens }) {
        const label = this.parser.parseInline(tokens)
        if (!href || !SAFE_HREF.test(href)) return label
        const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
        return `<a href="${escapeHtml(href)}"${titleAttr} target="_blank" rel="noopener noreferrer">${label}</a>`
      },
      image({ href, title, text }) {
        if (!images || !href || !SAFE_IMG_SRC.test(href)) return escapeHtml(text)
        const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
        return `<img src="${escapeHtml(href)}" alt="${escapeHtml(text)}"${titleAttr}>`
      },
    },
  })
  return md
}

const renderers = new Map<string, Marked>()

/** Render untrusted Markdown to HTML that is safe to inject. */
export function renderSafeMarkdown(markdown: string, options: SafeMarkdownOptions = {}): string {
  const { breaks = true, images = false } = options
  const key = `${breaks}|${images}`
  let md = renderers.get(key)
  if (!md) {
    md = buildRenderer(breaks, images)
    renderers.set(key, md)
  }
  return md.parse(markdown, { async: false }) as string
}
