import { afterEach, describe, expect, it, vi } from 'vitest'
import { createVectorization, createVectorizationBatch, getVectorizationPresets, type VectorizationOptions } from './api'

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
        model_metadata: { requested: true, provider: 'opencv', model_id: 'torchvision.deeplabv3-mobilenet-v3-large', version: 'COCO_WITH_VOC_LABELS_V1', fallback_reason: 'model-unavailable' },
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
      modelMetadata: { provider: 'opencv', modelId: 'torchvision.deeplabv3-mobilenet-v3-large', version: 'COCO_WITH_VOC_LABELS_V1', fallbackReason: 'model-unavailable' },
    })
  })

  it('serializes repeated images and maps per-file batch status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: 'batch-1',
      status: 'partial',
      total_count: 2,
      completed_count: 1,
      failed_count: 1,
      created_at: '2026-07-18T00:00:00Z',
      updated_at: '2026-07-18T00:01:00Z',
      items: [
        { id: 'job-1', status: 'completed', source_filename: 'icon.png', artifacts: { svg: '/api/v1/vectorizations/job-1/artifacts/svg' } },
        { id: 'job-2', status: 'failed', source_filename: 'broken.jpg', artifacts: {}, error_detail: 'No editable shapes were detected.' },
      ],
    }), { status: 202, headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const batch = await createVectorizationBatch(
      [new File(['one'], 'icon.png', { type: 'image/png' }), new File(['two'], 'broken.jpg', { type: 'image/jpeg' })],
      null,
      options,
      'batch-key',
    )

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit
    const form = request.body as FormData
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/vectorization-batches', expect.objectContaining({ headers: { 'Idempotency-Key': 'batch-key' } }))
    expect(form.getAll('images')).toHaveLength(2)
    expect(batch).toMatchObject({ id: 'batch-1', status: 'partial', totalCount: 2, completedCount: 1, failedCount: 1 })
    expect(batch.items[0]).toMatchObject({ id: 'job-1', sourceFilename: 'icon.png', artifacts: { svgUrl: '/api/v1/vectorizations/job-1/artifacts/svg' } })
    expect(batch.items[1]).toMatchObject({ id: 'job-2', status: 'failed', error: 'No editable shapes were detected.' })
  })

  it('maps server presets into inspector-friendly options', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([
      { id: 'flat-color-logo', label: 'Flat-color logo', description: 'Solid marks', options: { mode: 'illustration', color_count: 6, smoothing: 0.25, min_component_area: 24, use_segmentation_model: false } },
    ]), { status: 200, headers: { 'content-type': 'application/json' } })))

    await expect(getVectorizationPresets()).resolves.toEqual([{
      id: 'flat-color-logo',
      label: 'Flat-color logo',
      description: 'Solid marks',
      options: { mode: 'illustration', colorCount: 6, smoothing: 25, minimumComponentArea: 24, useSegmentation: false },
    }])
  })

  it('preserves a 404 status for a stale batch API image', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })))

    await expect(createVectorizationBatch(
      [new File(['image'], 'logo.png', { type: 'image/png' })],
      null,
      options,
      'missing-batch-api',
    )).rejects.toMatchObject({ name: 'ApiRequestError', status: 404 })
  })
})
