import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock the leaf deps so we assert the orchestration shape (post→read→runJob→writeback).
vi.mock('../../../../services/aiRouter', async () => {
  const actual = await vi.importActual<typeof import('../../../../services/aiRouter')>(
    '../../../../services/aiRouter',
  )
  return { ...actual, runJob: vi.fn().mockResolvedValue({ text: '- Storage\n- API' }) }
})
vi.mock('../../../../services/pathlyApi', () => ({
  readFile: vi.fn().mockResolvedValue('# Doc\n## Storage\nWAL.\n## API\nroutes.\n'),
}))
vi.mock('../../../../store/commsApi', () => ({
  fetchArtifacts: vi.fn().mockResolvedValue([{ id: 'art-1', path: '/p/DOC.md', type: 'md' }]),
  apiSetArtifactSummary: vi.fn().mockResolvedValue(true),
  apiGetDefaultSelection: vi.fn().mockResolvedValue(null),
}))

import * as aiRouter from '../../../../services/aiRouter'
import * as pathlyApi from '../../../../services/pathlyApi'
import * as commsApi from '../../../../store/commsApi'
import { AI_SELECTION_OFF } from '../../../../services/aiRouter'
import { summarizeArtifact } from './summarizeArtifact'

const runJob = aiRouter.runJob as ReturnType<typeof vi.fn>
const readFile = pathlyApi.readFile as ReturnType<typeof vi.fn>
const fetchArtifacts = commsApi.fetchArtifacts as ReturnType<typeof vi.fn>
const apiSetArtifactSummary = commsApi.apiSetArtifactSummary as ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  readFile.mockResolvedValue('# Doc\n## Storage\nWAL.\n')
  fetchArtifacts.mockResolvedValue([{ id: 'art-1', path: '/p/DOC.md', type: 'md' }])
  apiSetArtifactSummary.mockResolvedValue(true)
})

describe('summarizeArtifact', () => {
  it('reads the file, runs the chosen target, and writes the summary + selection back', async () => {
    const selection = { type: 'model' as const, id: 'phi-4-mini' }
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/DOC.md', atype: 'md', selection, cwd: 'C:/proj',
    })
    expect(ok).toBe(true)
    expect(readFile).toHaveBeenCalledWith('/p/DOC.md')
    expect(runJob).toHaveBeenCalledTimes(1)
    const [job, sel] = runJob.mock.calls[0]
    expect(job.kind).toBe('summarize')
    expect(job.cwd).toBe('C:/proj')
    expect(sel).toEqual(selection)
    expect(apiSetArtifactSummary).toHaveBeenCalledWith('art-1', '- Storage\n- API', selection)
  })

  it('skips summarization when the selection is Off', async () => {
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/DOC.md', atype: 'md', selection: AI_SELECTION_OFF,
    })
    expect(ok).toBe(false)
    expect(runJob).not.toHaveBeenCalled()
    expect(apiSetArtifactSummary).not.toHaveBeenCalled()
  })

  it('skips non-markdown artifacts (no summary attempted)', async () => {
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/diagram.png', atype: 'image',
      selection: { type: 'model', id: 'phi-4-mini' },
    })
    expect(ok).toBe(false)
    expect(readFile).not.toHaveBeenCalled()
    expect(runJob).not.toHaveBeenCalled()
  })

  it('returns false (no writeback) when the model yields empty text', async () => {
    runJob.mockResolvedValueOnce({ text: '   ' })
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/DOC.md', atype: 'md',
      selection: { type: 'model', id: 'phi-4-mini' },
    })
    expect(ok).toBe(false)
    expect(apiSetArtifactSummary).not.toHaveBeenCalled()
  })
})
