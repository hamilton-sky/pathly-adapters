import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock the leaf deps so we assert the orchestration shape (post→read→runJob→writeback).
vi.mock('../../../../services/aiRouter', async () => {
  const actual = await vi.importActual<typeof import('../../../../services/aiRouter')>(
    '../../../../services/aiRouter',
  )
  return {
    ...actual,
    runJob: vi.fn().mockResolvedValue({
      text: '## Description\nWhat it is. Why it matters.\n\n## Summary\n- Storage\n- API',
    }),
  }
})
vi.mock('../../../../services/pathlyApi', () => ({
  readFile: vi.fn().mockResolvedValue('# Doc\n## Storage\nWAL.\n## API\nroutes.\n'),
  deleteFile: vi.fn().mockResolvedValue(true),
}))
vi.mock('../../../../services/skillCompose', () => ({
  // Default: compose unreachable → the engine path falls back to the bare prompt.
  composeClientSkill: vi.fn().mockResolvedValue(null),
}))
vi.mock('../../../../store/commsApi', () => ({
  fetchArtifacts: vi.fn().mockResolvedValue([{ id: 'art-1', path: '/p/DOC.md', type: 'md' }]),
  apiEditMessage: vi.fn().mockResolvedValue(true),
  apiSetArtifactSummary: vi.fn().mockResolvedValue(true),
  apiGetDefaultSelection: vi.fn().mockResolvedValue(null),
  SUMMARY_STYLE_DEFAULT: 'topic-map',
}))

import * as aiRouter from '../../../../services/aiRouter'
import * as pathlyApi from '../../../../services/pathlyApi'
import * as commsApi from '../../../../store/commsApi'
import * as skillCompose from '../../../../services/skillCompose'
import { AI_SELECTION_OFF } from '../../../../services/aiRouter'
import { summarizeArtifact } from './summarizeArtifact'

const runJob = aiRouter.runJob as ReturnType<typeof vi.fn>
const readFile = pathlyApi.readFile as ReturnType<typeof vi.fn>
const composeClientSkill = skillCompose.composeClientSkill as ReturnType<typeof vi.fn>
const fetchArtifacts = commsApi.fetchArtifacts as ReturnType<typeof vi.fn>
const apiEditMessage = commsApi.apiEditMessage as ReturnType<typeof vi.fn>
const apiSetArtifactSummary = commsApi.apiSetArtifactSummary as ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  readFile.mockResolvedValue('# Doc\n## Storage\nWAL.\n')
  fetchArtifacts.mockResolvedValue([{ id: 'art-1', path: '/p/DOC.md', type: 'md' }])
  apiEditMessage.mockResolvedValue(true)
  apiSetArtifactSummary.mockResolvedValue(true)
  composeClientSkill.mockResolvedValue(null)
})

describe('summarizeArtifact', () => {
  it('coerces a stale local-model target to the CLI default, runs it, and writes back', async () => {
    // Summaries are CLI-only: a stale stored local-model target is coerced to {engine, claude}
    // (summarizeArtifact.ts). So the run + the persisted selection use the coerced target.
    const selection = { type: 'model' as const, id: 'phi-4-mini' }
    const coerced = { type: 'engine' as const, id: 'claude' }
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/DOC.md', atype: 'md', selection, cwd: 'C:/proj',
    })
    expect(ok).toBe(true)
    expect(readFile).toHaveBeenCalledWith('/p/DOC.md')
    expect(runJob).toHaveBeenCalledTimes(1)
    const [job, sel] = runJob.mock.calls[0]
    expect(job.kind).toBe('summarize')
    expect(job.cwd).toBe('C:/proj')
    expect(sel).toEqual(coerced)
    expect(apiEditMessage).toHaveBeenCalledWith('msg-1', 'What it is. Why it matters.')
    expect(apiSetArtifactSummary).toHaveBeenCalledWith('art-1', '- Storage\n- API', coerced)
  })

  it('engine target composes the depth skill and reads the file-captured summary', async () => {
    composeClientSkill.mockResolvedValueOnce('COMPOSED PROMPT')
    // Source text for the doc; the structured result is read from the sibling .summary file.
    readFile.mockImplementation((p: string) =>
      Promise.resolve(
        String(p).endsWith('.summary')
          ? '## Description\nEngine-written desc.\n\n## Summary\n- topic A\n- topic B'
          : '# Doc\n## Storage\nWAL.\n',
      ),
    )
    const selection = { type: 'engine' as const, id: 'claude' }
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/DOC.md', atype: 'md', selection, cwd: 'C:/proj',
    })
    expect(ok).toBe(true)
    expect(composeClientSkill).toHaveBeenCalledTimes(1)
    // Writeback uses the FILE content, not runJob's stdout tail.
    expect(apiEditMessage).toHaveBeenCalledWith('msg-1', 'Engine-written desc.')
    expect(apiSetArtifactSummary).toHaveBeenCalledWith('art-1', '- topic A\n- topic B', selection)
  })

  it('skips summarization when the selection is Off', async () => {
    const ok = await summarizeArtifact({
      messageId: 'msg-1', path: '/p/DOC.md', atype: 'md', selection: AI_SELECTION_OFF,
    })
    expect(ok).toBe(false)
    expect(runJob).not.toHaveBeenCalled()
    expect(apiSetArtifactSummary).not.toHaveBeenCalled()
    expect(apiEditMessage).not.toHaveBeenCalled()
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
