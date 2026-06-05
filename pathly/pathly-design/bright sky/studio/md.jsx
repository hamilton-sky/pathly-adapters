/* md.jsx — tiny dependency-free Markdown → HTML (headings, bold, italic,
   inline code, fenced code, ul/ol, paragraphs) + optional search highlight */

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inlineMd(text, hl) {
  let s = escapeHtml(text);
  // inline code first (protect)
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  // restore code
  s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
  if (hl) {
    const q = hl.trim();
    if (q) {
      const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
      // avoid breaking tags: only highlight in text segments
      s = s.replace(/(>|^)([^<]+)(?=<|$)/g, (m, pre, txt) => pre + txt.replace(re, '<span class="hl">$1</span>'));
    }
  }
  return s;
}

function renderMarkdown(md, hl) {
  const lines = md.split('\n');
  let html = '';
  let i = 0;
  let listType = null;
  const closeList = () => { if (listType) { html += `</${listType}>`; listType = null; } };

  while (i < lines.length) {
    const line = lines[i];

    // fenced code
    if (/^```/.test(line)) {
      closeList();
      const lang = line.slice(3).trim();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      html += `<pre><code>${escapeHtml(buf.join('\n'))}</code></pre>`;
      continue;
    }
    // headings
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      closeList();
      const lvl = m[1].length;
      html += `<h${lvl}>${inlineMd(m[2], hl)}</h${lvl}>`;
      i++; continue;
    }
    // unordered list
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (listType !== 'ul') { closeList(); html += '<ul>'; listType = 'ul'; }
      html += `<li>${inlineMd(m[1], hl)}</li>`;
      i++; continue;
    }
    // ordered list
    if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) {
      if (listType !== 'ol') { closeList(); html += '<ol>'; listType = 'ol'; }
      html += `<li>${inlineMd(m[1], hl)}</li>`;
      i++; continue;
    }
    // blank
    if (/^\s*$/.test(line)) { closeList(); i++; continue; }
    // paragraph
    closeList();
    html += `<p>${inlineMd(line, hl)}</p>`;
    i++;
  }
  closeList();
  return html;
}

window.MD = { renderMarkdown };
