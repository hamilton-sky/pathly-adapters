import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import styles from './MarkdownEditor.module.css'
import { keymap } from '@codemirror/view'
import { markdown } from '@codemirror/lang-markdown'
import { EditorState, Prec } from '@codemirror/state'
import { undo, redo } from '@codemirror/commands'
import { useTheme } from '../../useTheme'
import { collectMatches } from './searchEngine'
import type { FindOptions, MatchInfo, MatchRange } from './searchEngine'
import { searchHighlightField, setSearchMatches } from './searchHighlight'

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
}

export interface MarkdownEditorHandle {
  undo: () => void
  redo: () => void
  /** Run a fresh search and jump to the first match at/after the cursor. */
  applySearch: (opts: FindOptions) => MatchInfo
  findNext: () => MatchInfo
  findPrevious: () => MatchInfo
  /** Replace the active match (if the selection sits on one) and advance. */
  replaceCurrent: (replaceText: string) => MatchInfo
  replaceAll: (replaceText: string) => MatchInfo
  clearSearch: () => void
  focusEditor: () => void
  getSelectedText: () => string
}

const EMPTY_INFO: MatchInfo = { total: 0, current: 0 }

export const MarkdownEditor = forwardRef<MarkdownEditorHandle, MarkdownEditorProps>(
  function MarkdownEditor({ value, onChange }, ref) {
    const t = useTheme()
    const containerRef = useRef<HTMLDivElement>(null)
    const viewRef = useRef<EditorView | null>(null)
    const optsRef = useRef<FindOptions>({ query: '', caseSensitive: false, wholeWord: false, regexp: false })
    const onChangeRef = useRef(onChange)
    onChangeRef.current = onChange

    useImperativeHandle(ref, () => {
      function moveToMatch(matches: MatchRange[], index: number): MatchInfo {
        const view = viewRef.current
        if (!view) return EMPTY_INFO
        if (index < 0 || matches.length === 0) {
          view.dispatch({ effects: setSearchMatches.of({ ranges: matches, current: -1 }) })
          return { total: matches.length, current: 0 }
        }
        const m = matches[index]
        view.dispatch({
          selection: { anchor: m.from, head: m.to },
          effects: setSearchMatches.of({ ranges: matches, current: index }),
          scrollIntoView: true,
        })
        return { total: matches.length, current: index + 1 }
      }

      return {
        undo: () => { if (viewRef.current) undo(viewRef.current) },
        redo: () => { if (viewRef.current) redo(viewRef.current) },

        applySearch: (opts) => {
          optsRef.current = opts
          const view = viewRef.current
          if (!view) return EMPTY_INFO
          const matches = collectMatches(view.state, opts)
          if (matches.length === 0) return moveToMatch(matches, -1)
          const from = view.state.selection.main.from
          let idx = matches.findIndex((m) => m.from >= from)
          if (idx === -1) idx = 0
          return moveToMatch(matches, idx)
        },

        findNext: () => {
          const view = viewRef.current
          if (!view) return EMPTY_INFO
          const matches = collectMatches(view.state, optsRef.current)
          if (matches.length === 0) return moveToMatch(matches, -1)
          const from = view.state.selection.main.from
          let idx = matches.findIndex((m) => m.from > from)
          if (idx === -1) idx = 0
          return moveToMatch(matches, idx)
        },

        findPrevious: () => {
          const view = viewRef.current
          if (!view) return EMPTY_INFO
          const matches = collectMatches(view.state, optsRef.current)
          if (matches.length === 0) return moveToMatch(matches, -1)
          const from = view.state.selection.main.from
          let idx = -1
          for (let i = matches.length - 1; i >= 0; i--) {
            if (matches[i].from < from) { idx = i; break }
          }
          if (idx === -1) idx = matches.length - 1
          return moveToMatch(matches, idx)
        },

        replaceCurrent: (replaceText) => {
          const view = viewRef.current
          if (!view) return EMPTY_INFO
          const sel = view.state.selection.main
          const matches = collectMatches(view.state, optsRef.current)
          if (matches.length === 0) return moveToMatch(matches, -1)
          const curIdx = matches.findIndex((m) => m.from === sel.from && m.to === sel.to)
          if (curIdx === -1) {
            // Selection isn't on a match yet — treat Replace as "find next".
            let idx = matches.findIndex((m) => m.from >= sel.from)
            if (idx === -1) idx = 0
            return moveToMatch(matches, idx)
          }
          const m = matches[curIdx]
          view.dispatch({ changes: { from: m.from, to: m.to, insert: replaceText } })
          const after = collectMatches(view.state, optsRef.current)
          if (after.length === 0) return moveToMatch(after, -1)
          const pos = m.from + replaceText.length
          let nextIdx = after.findIndex((x) => x.from >= pos)
          if (nextIdx === -1) nextIdx = 0
          return moveToMatch(after, nextIdx)
        },

        replaceAll: (replaceText) => {
          const view = viewRef.current
          if (!view) return EMPTY_INFO
          const matches = collectMatches(view.state, optsRef.current)
          if (matches.length === 0) return moveToMatch(matches, -1)
          view.dispatch({ changes: matches.map((m) => ({ from: m.from, to: m.to, insert: replaceText })) })
          const after = collectMatches(view.state, optsRef.current)
          return moveToMatch(after, after.length > 0 ? 0 : -1)
        },

        clearSearch: () => {
          viewRef.current?.dispatch({ effects: setSearchMatches.of({ ranges: [], current: -1 }) })
        },

        focusEditor: () => { viewRef.current?.focus() },

        getSelectedText: () => {
          const view = viewRef.current
          if (!view) return ''
          const sel = view.state.selection.main
          return view.state.sliceDoc(sel.from, sel.to)
        },
      }
    }, [])

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
        },
        '.cm-find-match': {
          backgroundColor: `color-mix(in srgb, ${t.accent} 28%, transparent)`,
          borderRadius: '2px'
        },
        '.cm-find-match-current': {
          backgroundColor: `color-mix(in srgb, ${t.accent} 55%, transparent)`,
          borderRadius: '2px',
          outline: `1px solid ${t.accent}`
        }
      })

      // Swallow CodeMirror's built-in search panel (Mod-f / Mod-h from basicSetup)
      // so our own FindReplaceBar is the only find UI. Returning true also blocks
      // the browser's native find. Opening the bar is handled in useFindReplace.
      const suppressDefaultSearch = Prec.highest(
        keymap.of([
          { key: 'Mod-f', run: () => true },
          { key: 'Mod-h', run: () => true },
        ])
      )

      const view = new EditorView({
        state: EditorState.create({
          doc: value,
          extensions: [
            suppressDefaultSearch,
            basicSetup,
            markdown(),
            searchHighlightField,
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

    return <div ref={containerRef} className={styles.container} />
  }
)
