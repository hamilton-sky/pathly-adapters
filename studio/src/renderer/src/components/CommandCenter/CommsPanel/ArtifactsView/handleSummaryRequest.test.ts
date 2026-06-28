import { vi, describe, it, expect, beforeEach } from 'vitest'

// Mock the shared summarize core so we assert the handler's dispatch + guards, not
// the file-read/runJob plumbing (covered by summarizeArtifact.test.ts).
vi.mock('./summarizeArtifact', () => ({
  summarizeArtifactById: vi.fn().mockResolvedValue(true),
}))
vi.mock('../../../../store/projectStore', () => ({
  useProjectStore: { getState: () => ({ projectPath: 'C:/proj' }) },
}))
vi.mock('../../../../store/commsApi', () => ({
  apiGetDefaultStyle: vi.fn().mockResolvedValue(null),
}))

import * as core from './summarizeArtifact'
import { handleSummaryRequest } from './handleSummaryRequest'

const summarizeArtifactById = core.summarizeArtifactById as ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
  summarizeArtifactById.mockResolvedValue(true)
})

describe('handleSummaryRequest', () => {
  it('runs the resolved target for a valid summary_request', async () => {
    await handleSummaryRequest({
      artifact_id: 'art-9',
      message_id: 'msg-9',
      artifact_path: '/p/DOC.md',
      selection: { type: 'model', id: 'phi-4-mini' },
    })
    expect(summarizeArtifactById).toHaveBeenCalledTimes(1)
    const [messageId, id, path, sel, cwd] = summarizeArtifactById.mock.calls[0]
    expect(messageId).toBe('msg-9')
    expect(id).toBe('art-9')
    expect(path).toBe('/p/DOC.md')
    expect(sel).toEqual({ type: 'model', id: 'phi-4-mini' })
    expect(cwd).toBe('C:/proj')
  })

  it('skips when the selection is the Off sentinel', async () => {
    await handleSummaryRequest({
      artifact_id: 'art-off',
      message_id: 'msg-off',
      artifact_path: '/p/DOC.md',
      selection: { type: 'model', id: '__off__' },
    })
    expect(summarizeArtifactById).not.toHaveBeenCalled()
  })

  it('skips when the event is missing fields', async () => {
    await handleSummaryRequest({ artifact_path: '/p/DOC.md', selection: { type: 'model', id: 'x' } })
    await handleSummaryRequest({ artifact_id: 'a', selection: { type: 'model', id: 'x' } })
    await handleSummaryRequest({ artifact_id: 'a', message_id: 'm', artifact_path: '/p/DOC.md' })
    await handleSummaryRequest({ artifact_id: 'a', message_id: 'm', artifact_path: '/p/DOC.md', selection: { type: 'bogus', id: 'x' } })
    expect(summarizeArtifactById).not.toHaveBeenCalled()
  })

  it('dedupes: the same artifact is summarized at most once', async () => {
    const evt = {
      artifact_id: 'art-dup',
      message_id: 'msg-dup',
      artifact_path: '/p/DOC.md',
      selection: { type: 'model' as const, id: 'phi-4-mini' },
    }
    await handleSummaryRequest(evt)
    await handleSummaryRequest(evt)
    expect(summarizeArtifactById).toHaveBeenCalledTimes(1)
  })

  it('never throws when the core rejects', async () => {
    summarizeArtifactById.mockRejectedValueOnce(new Error('boom'))
    await expect(
      handleSummaryRequest({
        artifact_id: 'art-throw',
        message_id: 'msg-throw',
        artifact_path: '/p/DOC.md',
        selection: { type: 'model', id: 'phi-4-mini' },
      }),
    ).resolves.toBeUndefined()
  })
})
