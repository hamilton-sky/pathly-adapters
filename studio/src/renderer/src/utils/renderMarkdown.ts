function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function applyInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/<([^>]+)>/g, '<span class="var-hl">$1</span>')
}

export function renderMarkdown(md: string): string {
  const parts: string[] = []

  // Extract fenced code blocks first, replace with placeholders
  const placeholders: string[] = []
  const withoutCode = md.replace(/```[\s\S]*?```/g, (match) => {
    const inner = match.slice(3, -3)
    const newlineIdx = inner.indexOf('\n')
    const body = newlineIdx >= 0 ? inner.slice(newlineIdx + 1) : inner
    placeholders.push(`<pre><code>${escapeHtml(body)}</code></pre>`)
    return `\x00CODE${placeholders.length - 1}\x00`
  })

  const lines = withoutCode.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Code block placeholder
    const codeMatch = line.match(/^\x00CODE(\d+)\x00$/)
    if (codeMatch) {
      parts.push(placeholders[parseInt(codeMatch[1], 10)])
      i++
      continue
    }

    // Headings
    if (/^#### /.test(line)) { parts.push(`<h4>${applyInline(line.slice(5))}</h4>`); i++; continue }
    if (/^### /.test(line)) { parts.push(`<h3>${applyInline(line.slice(4))}</h3>`); i++; continue }
    if (/^## /.test(line)) { parts.push(`<h2>${applyInline(line.slice(3))}</h2>`); i++; continue }
    if (/^# /.test(line)) { parts.push(`<h1>${applyInline(line.slice(2))}</h1>`); i++; continue }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) { parts.push('<hr>'); i++; continue }

    // Blockquote
    if (/^> /.test(line)) {
      parts.push(`<blockquote>${applyInline(line.slice(2))}</blockquote>`)
      i++
      continue
    }

    // Unordered list
    if (/^[-*] /.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        items.push(`<li>${applyInline(lines[i].slice(2))}</li>`)
        i++
      }
      parts.push(`<ul>${items.join('')}</ul>`)
      continue
    }

    // Ordered list
    if (/^\d+\. /.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        const text = lines[i].replace(/^\d+\. /, '')
        items.push(`<li>${applyInline(text)}</li>`)
        i++
      }
      parts.push(`<ol>${items.join('')}</ol>`)
      continue
    }

    // Blank line — paragraph break (skip)
    if (line.trim() === '') {
      i++
      continue
    }

    // Paragraph: collect consecutive non-special lines
    const paraLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^#{1,4} /.test(lines[i]) &&
      !/^---+$/.test(lines[i].trim()) &&
      !/^> /.test(lines[i]) &&
      !/^[-*] /.test(lines[i]) &&
      !/^\d+\. /.test(lines[i]) &&
      !/^\x00CODE\d+\x00$/.test(lines[i])
    ) {
      paraLines.push(lines[i])
      i++
    }
    if (paraLines.length > 0) {
      parts.push(`<p>${applyInline(paraLines.join(' '))}</p>`)
    }
  }

  return parts.join('\n')
}
