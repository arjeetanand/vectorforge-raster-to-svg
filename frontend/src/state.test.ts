import { describe, expect, it } from 'vitest'
import { vectorPreviewUrl } from './api'
import { initialState, workbenchReducer } from './state'
import { recommendFromMetrics } from './recommendation'

describe('workbenchReducer', () => {
  it('shows the downloadable SVG instead of a separate raster preview', () => {
    expect(vectorPreviewUrl({ id: 'a1', status: 'completed', artifacts: { svgUrl: '/vector.svg', previewUrl: '/preview.png' } })).toBe('/vector.svg')
  })

  it('clears a previous result when the input changes', () => {
    const file = new File(['svg'], 'mark.png', { type: 'image/png' })
    const state = { ...initialState, job: { id: 'old', status: 'completed' as const, artifacts: {} } }
    const result = workbenchReducer(state, { type: 'file-selected', file, sourceUrl: 'blob:mark' })
    expect(result.file).toBe(file)
    expect(result.job).toBeNull()
    expect(result.error).toBeNull()
  })

  it('does not apply a stale recommendation after a second upload', () => {
    const first = new File(['first'], 'first.png', { type: 'image/png' })
    const second = new File(['second'], 'second.png', { type: 'image/png' })
    const selectedSecond = workbenchReducer(initialState, { type: 'file-selected', file: second, sourceUrl: 'blob:second' })
    const lineArt = recommendFromMetrics({ colorDiversity: 2, colorFamilyCount: 1, coloredPixelRatio: 0.08, saturatedPixelRatio: 0.08, inkCoverage: 0.12, averageBrightness: 242 })
    const result = workbenchReducer(selectedSecond, { type: 'recommendation-ready', file: first, sourceUrl: 'blob:first', recommendation: lineArt })
    expect(result).toBe(selectedSecond)
    expect(result.file).toBe(second)
    expect(result.job).toBeNull()
  })

  it('uses a line-art profile for sparse single-ink artwork', () => {
    const recommendation = recommendFromMetrics({ colorDiversity: 2, colorFamilyCount: 1, coloredPixelRatio: 0.08, saturatedPixelRatio: 0.08, inkCoverage: 0.12, averageBrightness: 242 })
    expect(recommendation.mode).toBe('line-art')
    expect(recommendation.options.minimumComponentArea).toBeGreaterThan(initialState.options.minimumComponentArea)
  })

  it('uses illustration for a colorful multi-region image', () => {
    const recommendation = recommendFromMetrics({ colorDiversity: 9, colorFamilyCount: 3, coloredPixelRatio: 0.42, saturatedPixelRatio: 0.42, inkCoverage: 0.64, averageBrightness: 148 })
    expect(recommendation.mode).toBe('illustration')
    expect(recommendation.options.colorCount).toBeGreaterThan(3)
  })

  it('warns when an image appears photo-like', () => {
    const recommendation = recommendFromMetrics({ colorDiversity: 32, colorFamilyCount: 7, coloredPixelRatio: 0.35, saturatedPixelRatio: 0.35, inkCoverage: 0.78, averageBrightness: 126 })
    expect(recommendation.message).toContain('photo-like')
    expect(recommendation.confidence).toBe('medium')
  })

  it('retains existing options while updating one inspector value', () => {
    const result = workbenchReducer(initialState, { type: 'options-updated', options: { smoothing: 70 } })
    expect(result.options.smoothing).toBe(70)
    expect(result.options.colorCount).toBe(initialState.options.colorCount)
  })

  it('recommends illustration for a sparse multi-colour logo on white', () => {
    const recommendation = recommendFromMetrics({ colorDiversity: 5, colorFamilyCount: 2, coloredPixelRatio: 0.06, saturatedPixelRatio: 0.05, inkCoverage: 0.09, averageBrightness: 243 })
    expect(recommendation.mode).toBe('illustration')
    expect(recommendation.options.colorCount).toBeGreaterThanOrEqual(3)
  })

  it('clears a completed output when vectorization settings change', () => {
    const completed = { ...initialState, job: { id: 'old', status: 'completed' as const, artifacts: { svgUrl: '/old.svg' } } }
    const result = workbenchReducer(completed, { type: 'options-updated', options: { mode: 'illustration' } })
    expect(result.options.mode).toBe('illustration')
    expect(result.job).toBeNull()
    expect(result.revectorizeRequired).toBe(true)
  })

  it('marks a created job as no longer submitting', () => {
    const loading = workbenchReducer(initialState, { type: 'submit-started' })
    const complete = workbenchReducer(loading, { type: 'job-updated', job: { id: 'a1', status: 'queued', artifacts: {} } })
    expect(complete.submitting).toBe(false)
    expect(complete.job?.id).toBe('a1')
  })

  it('restarts polling for a retained job after a status request fails', () => {
    const job = { id: 'a1', status: 'processing' as const, artifacts: {} }
    const failed = workbenchReducer({ ...initialState, job }, { type: 'request-failed', error: 'Network unavailable' })
    const retry = workbenchReducer(failed, { type: 'poll-retry-requested' })
    expect(retry.job).toBe(job)
    expect(retry.error).toBeNull()
    expect(retry.pollRetryAttempt).toBe(1)
  })
})
