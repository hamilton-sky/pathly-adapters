import { useEffect, useRef, useState } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { EditorState } from '@codemirror/state'
import * as jsYaml from 'js-yaml'
import type { FlowYaml } from '../../types'

interface Props {
  initialContent: string
  onParsed: (data: FlowYaml) => void
  onDirty: () => void
  onSave: (content: string) => void
  syncContent?: string | null
}

export function YamlView({ initialContent, onParsed, onDirty, onSave, syncContent }: Props): JSX.Element {
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
          '&': { backgroundColor: '#1e1e2e', color: '#cdd6f4', height: '100%' },
          '.cm-content': { fontFamily: 'monospace', fontSize: '13px' },
          '.cm-gutters': { backgroundColor: '#181825', color: '#6c7086', border: 'none' },
          '.cm-activeLine': { backgroundColor: '#313244' },
          '.cm-cursor': { borderLeftColor: '#cba6f7' }
        }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const content = update.state.doc.toString()
            latestContentRef.current = content
            try {
              const parsed = jsYaml.load(content) as FlowYaml
              setParseError(null)
              onParsed(parsed)
            } catch (e) {
              setParseError(e instanceof Error ? e.message : String(e))
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
    // Only run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // When syncContent changes (switching from visual), update the editor content
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

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden'
  },
  errorBanner: {
    backgroundColor: '#f38ba833',
    borderBottom: '1px solid #f38ba8',
    padding: '6px 12px',
    flexShrink: 0
  },
  errorText: {
    color: '#f38ba8',
    fontSize: '12px',
    fontFamily: 'monospace'
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'flex-end',
    padding: '6px 12px',
    backgroundColor: '#181825',
    borderBottom: '1px solid #313244',
    flexShrink: 0
  },
  saveBtn: {
    background: '#cba6f7',
    border: 'none',
    borderRadius: '4px',
    color: '#1e1e2e',
    cursor: 'pointer',
    padding: '4px 14px',
    fontSize: '13px',
    fontWeight: 600
  },
  saveBtnDisabled: {
    background: '#45475a',
    border: 'none',
    borderRadius: '4px',
    color: '#6c7086',
    cursor: 'not-allowed',
    padding: '4px 14px',
    fontSize: '13px',
    fontWeight: 600
  },
  editor: {
    flex: 1,
    overflow: 'auto'
  }
}
