import { describe, expect, it } from 'vitest'
import { renderSafeMarkdown } from './safeMarkdown'

describe('renderSafeMarkdown', () => {
  it('renders the Markdown a model answers with', () => {
    const html = renderSafeMarkdown('### Pending\n- **PRE-C** gate\n- `lum doctor`')
    expect(html).toContain('<h3')
    expect(html).toContain('<strong>PRE-C</strong>')
    expect(html).toContain('<li>')
    expect(html).toContain('<code>lum doctor</code>')
  })

  it('escapes raw HTML instead of injecting it', () => {
    const html = renderSafeMarkdown('Hi <img src=x onerror="alert(1)"> and <script>alert(2)</script>')
    expect(html).not.toMatch(/<img|<script/i)
    expect(html).toContain('&lt;img')
    expect(html).toContain('&lt;script&gt;')
  })

  it('drops javascript: and other unsafe links, keeping the label', () => {
    for (const md of ['[click](javascript:alert(1))', '<javascript:alert(1)>', '[x](data:text/html,<b>)']) {
      expect(renderSafeMarkdown(md)).not.toMatch(/href=/i)
    }
    expect(renderSafeMarkdown('[click](javascript:alert(1))')).toContain('click')
  })

  it('keeps http(s) links, opening externally', () => {
    const html = renderSafeMarkdown('[docs](https://example.com/a?b=1&c="2")')
    expect(html).toContain('href="https://example.com/a?b=1&amp;c=&quot;2&quot;"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('shows images as alt text', () => {
    const html = renderSafeMarkdown('![diagram](https://evil.example/x.png)')
    expect(html).not.toMatch(/<img/i)
    expect(html).toContain('diagram')
  })

  it('renders safe images only when asked, never svg or script sources', () => {
    const opts = { images: true }
    expect(renderSafeMarkdown('![d](https://example.com/d.png "t")', opts)).toContain(
      '<img src="https://example.com/d.png" alt="d" title="t">',
    )
    expect(renderSafeMarkdown('![d](data:image/png;base64,AAAA)', opts)).toContain('<img src="data:image/png')
    for (const md of ['![d](javascript:alert(1))', '![d](data:image/svg+xml;base64,AAAA)', '![d](file:///etc/x.png)']) {
      expect(renderSafeMarkdown(md, opts)).not.toMatch(/<img/i)
    }
  })

  it('escapes image alt text that tries to break out of the attribute', () => {
    const html = renderSafeMarkdown('![" onerror="alert(1)](https://example.com/d.png)', { images: true })
    expect(html).not.toMatch(/onerror="alert/)
  })

  it('is the only renderer module that imports marked', () => {
    const sources = import.meta.glob('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true })
    const importers = Object.entries(sources)
      .filter(([, src]) => /from\s+['"]marked['"]/.test(src as string))
      .map(([path]) => path)
    expect(importers).toEqual(['./safeMarkdown.ts'])
  })

  it('breaks: false keeps plain marked line handling', () => {
    expect(renderSafeMarkdown('a\nb')).toContain('<br>')
    expect(renderSafeMarkdown('a\nb', { breaks: false })).not.toContain('<br>')
  })
})
