import { useEffect, useRef, useState } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { EditorState } from '@codemirror/state'
import * as jsYaml from 'js-yaml'
import { useTheme } from '../../../useTheme'
import type { FlowYaml } from '../../../types'
import { makeYamlViewStyles } from './YamlView.styles'

interface Props {
  initialContent: string
  onParsed: (data: FlowYaml) => void
  onParseError?: (err: string | null) => void
  onDirty: () => void
  onSave: (content: string) => void
  syncContent?: string | null
}

export function YamlView({ initialContent, onParsed, onParseError, onDirty, onSave, syncContent }: Props): JSX.Element {
  const t = useTheme()
  const styles = makeYamlViewStyles(t)
  const containerRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const latestContentRef = useRef(initialContent)

  useEffect(() => {
    if (!containerRef.current) return

    const state = EditorState.create({
      doc: initialContent,
      extensions: [
        basicSetup,
        yaml(),
        EditorView.theme({
          '&': { backgroundColor: t.bgBase, color: t.textPrimary, height: '100%' },
          '.cm-content': { fontFamily: 'monospace', fontSize: '13px' },
          '.cm-gutters': { backgroundColor: t.bgMantle, color: t.textMuted, border: 'none' },
          '.cm-activeLine': { backgroundColor: t.bgSurface0 },
          '.cm-cursor': { borderLeftColor: t.accent }
        }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const content = update.state.doc.toString()
            latestContentRef.current = content
            try {
              const parsed = jsYaml.load(content) as FlowYaml
              setParseError(null)
              onParseError?.(null)
              onParsed(parsed)
            } catch (e) {
              const msg = e instanceof Error ? e.message : String(e)
              setParseError(msg)
              onParseError?.(msg)
            }
            onDirty()
          }
        })
      ]
    })

    const view = new EditorView({ state, parent: containerRef.current })
    viewRef.current = view

    return () => {
      view.destroy()
      viewRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (syncContent == null) return
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current === syncContent) return
    view.dispatch({
      changes: { from: 0, to: current.length, insert: syncContent }
    })
  }, [syncContent])

  function handleSave(): void {
    onSave(latestContentRef.current)
  }

  return (
    <div style={styles.wrapper}>
      {parseError && (
        <div style={styles.errorBanner}>
          <span style={styles.errorText}>YAML parse error: {parseError}</span>
        </div>
      )}
      <div style={styles.toolbar}>
        <button
          style={parseError ? styles.saveBtnDisabled : styles.saveBtn}
          onClick={handleSave}
          disabled={!!parseError}
        >
          Save
        </button>
      </div>
      <div ref={containerRef} style={styles.editor} />
    </div>
  )
}
