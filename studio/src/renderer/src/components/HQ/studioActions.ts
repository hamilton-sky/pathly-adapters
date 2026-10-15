// The HQ operator actions Studio itself runs (pathly/features/local-operator,
// ticket 01: "diagrams run in Studio"). The server has already validated the
// card and resolved its target (POST /hq/actions/run → approved); this reuses
// the editor's own diagram code, then the caller reports the result for audit.
import { loadEditorCli, loadPreset } from '../MarkdownEditor/EditorHeader/editorCli'
import { CLI_KEY_DIAGRAM, PRESET_KEY_DIAGRAM } from '../MarkdownEditor/EditorHeader/diagramPresets'
import { diagramPromptForStyle, resolveDiagramPrompt, startDiagramRun } from '../MarkdownEditor/EditorHeader/hooks/diagramRun'
import { markDiagramOnBoard, readSidecar } from '../MarkdownEditor/DiagramGalleryPanel/diagramSidecar'
import { addDiagramToBoard } from '../MarkdownEditor/DiagramGalleryPanel/addDiagramToBoard'

export interface StudioOutcome {
  ok: boolean
  summary: string
}

interface Where {
  board: string
  projectRoot: string | null
}

async function diagramArtifact(target: Record<string, unknown>): Promise<StudioOutcome> {
  const path = String(target.path ?? '')
  const style = typeof target.style === 'string' ? target.style : null
  const title = String(target.title || path.split('/').pop() || 'the artifact')
  // No style asked for: the editor's own choice (its saved preset / prompt).
  const prompt = style
    ? diagramPromptForStyle(style, path)
    : resolveDiagramPrompt(null, loadPreset(PRESET_KEY_DIAGRAM), path)
  const started = await startDiagramRun(path, prompt, loadEditorCli(CLI_KEY_DIAGRAM))
  if (started === 'launched') return { ok: true, summary: `Diagram agent started on “${title}”` }
  if (started === 'busy') return { ok: false, summary: 'Failed: a diagram is already running for that file' }
  return { ok: false, summary: 'Failed: the diagram agent could not start' }
}

async function addToBoard(target: Record<string, unknown>, where: Where): Promise<StudioOutcome> {
  const path = String(target.path ?? '')
  const sidecar = await readSidecar(path)
  const entry = sidecar?.diagrams.find((d) => d.id === target.diagram_id)
  if (!entry) return { ok: false, summary: 'Failed: that diagram is gone' }
  const board = { feature: where.board, board: 'feature', scope: where.board }
  const id = await addDiagramToBoard(path, entry, board, where.projectRoot ?? undefined)
  if (!id) return { ok: false, summary: 'Failed: could not post the diagram' }
  await markDiagramOnBoard(path, entry.id, { id, at: new Date().toISOString() })
  return { ok: true, summary: `Added diagram “${entry.title || entry.style}” to ${where.board}` }
}

/** Run an approved Studio-side action. Never throws. */
export async function runStudioAction(name: string, target: Record<string, unknown>, where: Where): Promise<StudioOutcome> {
  try {
    if (name === 'diagram_artifact') return await diagramArtifact(target)
    if (name === 'add_diagram_to_board') return await addToBoard(target, where)
    return { ok: false, summary: `Failed: ${name} does not run in Studio` }
  } catch (err) {
    return { ok: false, summary: `Failed: ${err instanceof Error ? err.message : String(err)}` }
  }
}
