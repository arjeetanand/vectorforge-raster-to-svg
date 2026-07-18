export type VectorizationMode = 'line-art' | 'illustration'
export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface VectorizationOptions {
  mode: VectorizationMode
  colorCount: number
  smoothing: number
  minimumComponentArea: number
  useSegmentation: boolean
}

export interface VectorizationArtifacts {
  sourceUrl?: string
  svgUrl?: string
  previewUrl?: string
  comparisonUrl?: string
}

export interface VectorizationJob {
  id: string
  status: JobStatus
  createdAt?: string
  updatedAt?: string
  options?: Partial<VectorizationOptions>
  artifacts: VectorizationArtifacts
  modelUsed?: string
  error?: string
}

interface ApiJob {
  id: string
  status: JobStatus
  created_at?: string
  updated_at?: string
  options?: Partial<Record<'mode' | 'color_count' | 'smoothing' | 'min_component_area' | 'use_segmentation_model', string | number | boolean>>
  artifacts?: Partial<Record<'original' | 'svg' | 'preview' | 'comparison', string>>
  model_used?: string
  error_detail?: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

function apiPath(path: string): string {
  return `${API_BASE.replace(/\/$/, '')}${path}`
}

function mapJob(job: ApiJob): VectorizationJob {
  const options = job.options
  return {
    id: job.id,
    status: job.status,
    createdAt: job.created_at,
    updatedAt: job.updated_at,
    options: options
      ? {
          mode: options.mode as VectorizationMode | undefined,
          colorCount: Number(options.color_count),
          smoothing: Number(options.smoothing) * 100,
          minimumComponentArea: Number(options.min_component_area),
          useSegmentation: options.use_segmentation_model === true || options.use_segmentation_model === 'true',
        }
      : undefined,
    artifacts: {
      sourceUrl: job.artifacts?.original,
      svgUrl: job.artifacts?.svg,
      previewUrl: job.artifacts?.preview,
      comparisonUrl: job.artifacts?.comparison,
    },
    modelUsed: job.model_used,
    error: job.error_detail,
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail ?? `Request failed (${response.status})`
  } catch {
    return `Request failed (${response.status})`
  }
}

export async function createVectorization(file: File, options: VectorizationOptions, signal?: AbortSignal): Promise<VectorizationJob> {
  const body = new FormData()
  body.append('image', file)
  body.append('mode', options.mode)
  body.append('color_count', String(options.colorCount))
  body.append('smoothing', String(options.smoothing / 100))
  body.append('min_component_area', String(options.minimumComponentArea))
  body.append('use_segmentation_model', String(options.useSegmentation))
  const response = await fetch(apiPath('/vectorizations'), { method: 'POST', body, signal })
  if (!response.ok) throw new Error(await parseError(response))
  return mapJob((await response.json()) as ApiJob)
}

export async function getVectorization(id: string, signal?: AbortSignal): Promise<VectorizationJob> {
  const response = await fetch(apiPath(`/vectorizations/${encodeURIComponent(id)}`), { signal })
  if (!response.ok) throw new Error(await parseError(response))
  return mapJob((await response.json()) as ApiJob)
}
