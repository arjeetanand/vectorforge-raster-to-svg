import { describe, expect, it } from 'vitest'
import { initialState, workbenchReducer } from './state'

describe('workbenchReducer', () => {
  it('clears a previous result when the input changes', () => {
    const file = new File(['svg'], 'mark.png', { type: 'image/png' })
    const state = { ...initialState, job: { id: 'old', status: 'completed' as const, artifacts: {} } }
    const result = workbenchReducer(state, { type: 'file-selected', file, sourceUrl: 'blob:mark' })
    expect(result.file).toBe(file)
    expect(result.job).toBeNull()
    expect(result.error).toBeNull()
  })

  it('retains existing options while updating one inspector value', () => {
    const result = workbenchReducer(initialState, { type: 'options-updated', options: { smoothing: 70 } })
    expect(result.options.smoothing).toBe(70)
    expect(result.options.colorCount).toBe(initialState.options.colorCount)
  })

  it('marks a created job as no longer submitting', () => {
    const loading = workbenchReducer(initialState, { type: 'submit-started' })
    const complete = workbenchReducer(loading, { type: 'job-updated', job: { id: 'a1', status: 'queued', artifacts: {} } })
    expect(complete.submitting).toBe(false)
    expect(complete.job?.id).toBe('a1')
  })
})
