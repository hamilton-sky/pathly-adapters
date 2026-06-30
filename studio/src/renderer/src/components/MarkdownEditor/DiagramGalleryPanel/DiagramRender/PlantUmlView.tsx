// PlantUML has no in-process JS renderer, so by default we show the source. On explicit click
// ("Render via <host>") we encode the source and load the SVG from a PlantUML/Kroki server —
// the destination is named on the button, so clicking is informed consent. The server URL is
// configurable (localStorage 'pathly:plantumlServer'); default is the public plantuml.com.

import React, { useState } from 'react'
import { AlertTriangle, ExternalLink } from 'lucide-react'
import encoder from 'plantuml-encoder'
import styles from './DiagramRender.module.css'

const DEFAULT_SERVER = 'https://www.plantuml.com/plantuml'

function serverUrl(): string {
  try {
    return localStorage.getItem('pathly:plantumlServer')?.trim() || DEFAULT_SERVER
  } catch {
    return DEFAULT_SERVER
  }
}

function hostOf(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

interface Props {
  content: string
}

export default function PlantUmlView({ content }: Props) {
  const [render, setRender] = useState(false)
  const [failed, setFailed] = useState(false)
  const base = serverUrl()

  if (render && !failed) {
    const src = `${base.replace(/\/$/, '')}/svg/${encoder.encode(content)}`
    return (
      <div className={styles.svgHost}>
        {/* External image; the user opted in by clicking Render. */}
        <img className={styles.umlImg} src={src} alt="PlantUML diagram" onError={() => setFailed(true)} />
      </div>
    )
  }

  return (
    <>
      <pre className={styles.mono}>{content}</pre>
      <div className={styles.notice}>
        <AlertTriangle size={12} />
        {failed ? `Couldn’t reach ${hostOf(base)}.` : 'PlantUML isn’t rendered locally.'}
        <button
          type="button"
          className={styles.noticeBtn}
          onClick={() => {
            setFailed(false)
            setRender(true)
          }}
        >
          <ExternalLink size={11} />
          {failed ? 'Retry' : `Render via ${hostOf(base)}`}
        </button>
      </div>
    </>
  )
}
