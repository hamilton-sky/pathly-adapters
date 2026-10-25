// State + actions for the Chief launcher: the styles and the open session come from the server
// (GET /chief/presets, GET /chief/session), fetched each time the launcher mounts (it opens).
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  closeChief,
  fetchChiefPresets,
  fetchChiefSession,
  openChief,
  type ChiefPresetList,
  type ChiefSession,
} from '../../../../services/chiefApi'
import { saveUserPrompt } from '../../../../services/promptLibrary'
import { useTerminalStore } from '../../../../store/terminalStore'
import {
  loadEditorCli,
  loadPreset,
  saveEditorCli,
  savePreset,
  type EditorCli,
} from '../../../MarkdownEditor/EditorHeader/editorCli'
import {
  CLI_KEY_CHIEF,
  DEFAULT_CHIEF_PRESET,
  PRESET_KEY_CHIEF,
  editedPrompt,
  isChiefEngine,
  styleFileName,
  withTierLine,
} from '../chiefLauncherUtils'

export function useChiefLauncher(projectRoot: string, onOpened: () => void) {
  const [list, setList] = useState<ChiefPresetList | null>(null)
  const [session, setSession] = useState<ChiefSession | null>(null)
  const [selected, setSelected] = useState(() => loadPreset(PRESET_KEY_CHIEF, DEFAULT_CHIEF_PRESET))
  const [promptText, setPromptText] = useState('')
  const [cli, setCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_CHIEF))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!projectRoot) return
    let cancelled = false
    setError(null)
    void Promise.all([fetchChiefPresets(projectRoot), fetchChiefSession(projectRoot)]).then(
      ([presets, sess]) => {
        if (cancelled) return
        setList(presets)
        setSession(sess)
        if (!presets) setError('Could not reach the Pathly server.')
      },
    )
    return () => {
      cancelled = true
    }
  }, [projectRoot, nonce])

  const presets = useMemo(() => list?.presets ?? [], [list])
  const current = presets.find((p) => p.name === selected) ?? presets[0]

  // Show the chosen style's text whenever the list (re)loads or the choice changes.
  useEffect(() => {
    if (current) setPromptText(current.text)
  }, [current])

  const selectPreset = useCallback((name: string) => {
    setSelected(name)
    savePreset(PRESET_KEY_CHIEF, name)
  }, [])

  const changeCli = useCallback((next: EditorCli) => {
    setCli(next)
    saveEditorCli(CLI_KEY_CHIEF, next)
  }, [])

  const reset = useCallback(() => {
    if (current) setPromptText(current.text)
  }, [current])

  const open = useCallback(async () => {
    if (!current || busy) return
    if (!isChiefEngine(cli)) {
      setError('A chief runs on claude or codex. Pick one of them as the engine.')
      return
    }
    setBusy(true)
    setError(null)
    const res = await openChief({
      projectRoot,
      engine: cli,
      preset: current.name,
      prompt: editedPrompt(promptText, current),
    })
    setBusy(false)
    if (res.ok) {
      onOpened()
      return
    }
    setError(res.error)
    if (res.status === 409) setNonce((n) => n + 1)
  }, [busy, cli, current, onOpened, projectRoot, promptText])

  const close = useCallback(async () => {
    setBusy(true)
    const closed = await closeChief(projectRoot)
    setBusy(false)
    if (closed === null) setError('Could not close the chief.')
    setNonce((n) => n + 1)
  }, [projectRoot])

  const showTab = useCallback(() => {
    if (session?.open) useTerminalStore.getState().openTab(session.tab_id)
  }, [session])

  const saveStyle = useCallback(
    async (name: string) => {
      const file = styleFileName(name)
      if (!file || !current) return
      const saved = await saveUserPrompt({
        kind: 'preset',
        category: 'chief',
        name: file,
        label: name.trim(),
        body: withTierLine(promptText, current.tier),
        projectRoot,
      })
      if (!saved) {
        setError('Could not save the style.')
        return
      }
      selectPreset(file)
      setNonce((n) => n + 1)
    },
    [current, projectRoot, promptText, selectPreset],
  )

  return {
    list,
    presets,
    current,
    session,
    promptText,
    setPromptText,
    cli,
    changeCli,
    selectPreset,
    reset,
    open,
    close,
    showTab,
    saveStyle,
    busy,
    error,
  }
}
