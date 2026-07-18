import { afterEach, describe, expect, it, vi } from 'vitest'
import { createVectorization, type VectorizationOptions } from './api'

const options: VectorizationOptions = {
  mode: 'illustration',
  colorCount: 4,
  smoothing: 50,
  minimumComponentArea: 24,
  useSegmentation: false,
}

describe('createVectorization', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends the supplied idempotency key and maps quality diagnostics', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: 'job-1',
      status: 'completed',
      artifacts: {},
      quality: {
        score: 84,
        level: 'good',
        warnings: [],
        foreground_coverage: 0.32,
        path_count: 4,
        retained_color_count: 2,
        removed_component_count: 3,
        visual_similarity: 0.92,
        svg_complexity: { command_count: 16, path_data_characters: 240, level: 'low' },
        model_metadata: { requested: true, provider: 'opencv', fallback_reason: 'model-unavailable' },
      },
    }), { status: 202, headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const job = await createVectorization(
      new File(['image'], 'logo.png', { type: 'image/png' }),
      options,
      'same-request-key',
    )

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/vectorizations',
      expect.objectContaining({ headers: { 'Idempotency-Key': 'same-request-key' } }),
    )
    expect(job.quality).toMatchObject({
      score: 84,
      pathCount: 4,
      visualSimilarity: 0.92,
      svgComplexity: { level: 'low' },
      modelMetadata: { provider: 'opencv', fallbackReason: 'model-unavailable' },
    })
  })
})
