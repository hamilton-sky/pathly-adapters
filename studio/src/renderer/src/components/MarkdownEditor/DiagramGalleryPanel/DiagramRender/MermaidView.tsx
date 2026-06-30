// Lazy Mermaid renderer. The `mermaid` chunk (~500KB) is imported on first use and
// cached at module scope. We theme it from the live tokens.css custom properties, so
// flipping the Studio theme (the `theme` dep) re-initialises and re-renders with the
// new colours — satisfying the "theme re-render" story.
//
// securityLevel:'strict' because the diagram source comes from an agent (untrusted).
//
// Path assumes: src/components/MarkdownEditor/DiagramGalleryPanel/DiagramRender/MermaidView.tsx

import React, { useEffect, useRef, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useUiStore } from '../../../../store/uiStore'
import { repairMermaid, mermaidErrorHint } from './mermaidSafety'
import styles from './DiagramRender.module.css'

// Cache the dynamic import so the chunk is fetched + evaluated only once.
let mermaidPromise: Promise<typeof import('mermaid').default> | null = null
function loadMermaid() {
  if (!mermaidPromise) mermaidPromise = import('mermaid').then((m) => m.default)
  return mermaidPromise
}

// Monotonic id source so concurrent renders never collide on the same DOM id.
let renderSeq = 0

interface Props {
  id: string
  content: string
}

function tokenValue(cs: CSSStyleDeclaration, name: string, fallback: string): string {
  return cs.getPropertyValue(name).trim() || fallback
}

export default function MermaidView({ id, content }: Props) {
  const theme = useUiStore((s) => s.theme)
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    setError(null)

    void loadMermaid()
      .then(async (mermaid) => {
        const cs = getComputedStyle(document.documentElement)
        mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          securityLevel: 'strict',
          fontFamily: tokenValue(cs, '--font-family-base', 'sans-serif'),
          themeVariables: {
            background: tokenValue(cs, '--bg-base', '#111827'),
            primaryColor: tokenValue(cs, '--bg-surface0', '#1E2433'),
            primaryBorderColor: tokenValue(cs, '--border-color', '#283044'),
            primaryTextColor: tokenValue(cs, '--text-primary', '#E2E8F0'),
            lineColor: tokenValue(cs, '--text-muted', '#8899B0'),
            secondaryColor: tokenValue(cs, '--bg-surface1', '#283044'),
            tertiaryColor: tokenValue(cs, '--bg-mantle', '#0B0F1A'),
            fontSize: '13px',
          },
        })
        const renderId = `mmd_${id}_${renderSeq++}`
        // Safety net: repair near-miss / already-saved diagrams (e.g. a reserved word used as
        // a node id) before rendering. A no-op on already-valid source.
        const { svg: out } = await mermaid.render(renderId, repairMermaid(content))
        if (active) setSvg(out)
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : 'Failed to render diagram')
      })

    return () => {
      active = false
    }
  }, [id, content, theme])

  if (error) {
    // Surface WHY it failed instead of silently showing raw text. repairMermaid already
    // auto-fixes the common flowchart/mindmap reserved-word slips; mermaidErrorHint adds a
    // targeted tip for the sequence case (which is too ambiguous to auto-rewrite safely).
    const hint = mermaidErrorHint(content)
    return (
      <>
        <pre className={styles.mono} data-mermaid-error>
          {content}
        </pre>
        <div className={styles.notice}>
          <AlertTriangle size={12} />
          {hint ?? `Mermaid couldn’t render this diagram: ${error}`}
        </div>
      </>
    )
  }

  if (svg == null) {
    return <div className={styles.placeholder}>Rendering…</div>
  }

  return (
    <div
      ref={hostRef}
      className={styles.svgHost}
      // Mermaid output only — sanitised by mermaid's strict securityLevel.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
