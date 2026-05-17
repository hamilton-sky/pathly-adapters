import { useEffect, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorState } from '@codemirror/state'
import { useTheme } from '../../useTheme'

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
}

export function MarkdownEditor({ value, onChange }: MarkdownEditorProps): JSX.Element {
  const t = useTheme()
  const containerRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!containerRef.current) return

    const editorTheme = EditorView.theme({
      '&': {
        height: '100%',
        fontSize: '14px',
        backgroundColor: t.bgBase,
        color: t.textPrimary
      },
      '.cm-content': {
        padding: '12px',
        fontFamily: "'Fira Mono', 'Cascadia Code', monospace",
        caretColor: t.accent
      },
      '.cm-gutters': {
        backgroundColor: t.bgMantle,
        color: t.textMuted,
        border: 'none',
        borderRight: `1px solid ${t.bgSurface0}`
      },
      '.cm-activeLine': { backgroundColor: t.bgSurface0 },
      '.cm-selectionBackground, .cm-focused .cm-selectionBackground': {
        backgroundColor: t.bgSurface1
      }
    })

    const view = new EditorView({
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          markdown(),
          editorTheme,
          EditorView.updateListener.of((update) => {
            if (update.docChanged) {
              onChangeRef.current(update.state.doc.toString())
            }
          })
        ]
      }),
      parent: containerRef.current
    })

    viewRef.current = view

    return () => {
      view.destroy()
      viewRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current !== value) {
      view.dispatch({
        changes: { from: 0, to: current.length, insert: value }
      })
    }
  }, [value])

  return <div ref={containerRef} style={{ height: '100%', overflow: 'auto' }} />
}
