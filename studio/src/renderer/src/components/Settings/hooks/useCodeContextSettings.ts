import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../../../lib/config'
import { useToastStore } from '../../../store/toastStore'

export type CodeContextBackend = 'auto' | 'off' | 'cli' | 'lsp' | 'both'
export type CodeContextReindex = 'off' | 'stage' | 'auto'
export type CodeContextTool = 'codebase-memory-mcp'

const KEY_BACKEND = 'code_context.backend'
const KEY_REINDEX = 'code_context.reindex'
const KEY_TOOL    = 'code_context.tool'

const DEFAULT_BACKEND: CodeContextBackend = 'auto'
const DEFAULT_REINDEX: CodeContextReindex = 'auto'
const DEFAULT_TOOL: CodeContextTool       = 'codebase-memory-mcp'

function parseBackend(v: string | undefined): CodeContextBackend {
  return v === 'off' || v === 'cli' || v === 'lsp' || v === 'both' || v === 'auto'
    ? v
    : DEFAULT_BACKEND
}

function parseReindex(v: string | undefined): CodeContextReindex {
  if (v === 'stage' || v === 'auto') return v
  return DEFAULT_REINDEX
}

function parseTool(_v: string | undefined): CodeContextTool {
  // codebase-memory-mcp is the only supported tool (gitnexus removed); any legacy value maps to it.
  return DEFAULT_TOOL
}

interface CodeContextSettings {
  backend: CodeContextBackend
  reindex: CodeContextReindex
  tool: CodeContextTool
  setBackend: (v: CodeContextBackend) => void
  setReindex: (v: CodeContextReindex) => void
  setTool: (v: CodeContextTool) => void
}

export function useCodeContextSettings(): CodeContextSettings {
  const [backend, setBackendState] = useState<CodeContextBackend>(DEFAULT_BACKEND)
  const [reindex, setReindexState] = useState<CodeContextReindex>(DEFAULT_REINDEX)
  const [tool, setToolState]       = useState<CodeContextTool>(DEFAULT_TOOL)
  const pushToast = useToastStore((s) => s.push)

  useEffect(() => {
    apiFetch('/db/settings')
      .then((r) => r.json() as Promise<Record<string, string>>)
      .then((settings) => {
        setBackendState(parseBackend(settings[KEY_BACKEND]))
        setReindexState(parseReindex(settings[KEY_REINDEX]))
        setToolState(parseTool(settings[KEY_TOOL]))
      })
      .catch(() => {/* keep defaults on fetch failure */})
  }, [])

  function writeSetting(key: string, value: string): Promise<void> {
    return apiFetch(`/db/settings/${key}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    }).then(() => undefined)
  }

  const setBackend = useCallback((next: CodeContextBackend) => {
    const prev = backend
    setBackendState(next)
    writeSetting(KEY_BACKEND, next).catch(() => {
      setBackendState(prev)
      pushToast('Failed to save code intelligence setting', 'error')
    })
  }, [backend, pushToast])

  const setReindex = useCallback((next: CodeContextReindex) => {
    const prev = reindex
    setReindexState(next)
    writeSetting(KEY_REINDEX, next).catch(() => {
      setReindexState(prev)
      pushToast('Failed to save re-index setting', 'error')
    })
  }, [reindex, pushToast])

  const setTool = useCallback((next: CodeContextTool) => {
    const prev = tool
    setToolState(next)
    writeSetting(KEY_TOOL, next).catch(() => {
      setToolState(prev)
      pushToast('Failed to save code intelligence tool setting', 'error')
    })
  }, [tool, pushToast])

  return { backend, reindex, tool, setBackend, setReindex, setTool }
}
