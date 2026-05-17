import { useEffect, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorState } from '@codemirror/state'

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
}

const editorTheme = EditorView.theme({
  '&': {
    height: '100%',
    fontSize: '14px',
    backgroundColor: '#1e1e2e',
    color: '#cdd6f4'
  },
  '.cm-content': {
    padding: '12px',
    fontFamily: "'Fira Mono', 'Cascadia Code', monospace",
    caretColor: '#cba6f7'
  },
  '.cm-gutters': {
    backgroundColor: '#181825',
    color: '#6c7086',
    border: 'none',
    borderRight: '1px solid #313244'
  },
  '.cm-activeLine': { backgroundColor: '#313244' },
  '.cm-selectionBackground, .cm-focused .cm-selectionBackground': {
    backgroundColor: '#45475a'
  }
})

export function MarkdownEditor({ value, onChange }: MarkdownEditorProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!containerRef.current) return

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
  }, [])

  // Sync external value changes (e.g. when a different file is loaded)
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
