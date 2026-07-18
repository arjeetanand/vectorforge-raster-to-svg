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

export type QualityLevel = 'good' | 'review' | 'unsupported'

/** Explainable processing indicators, not a guarantee of artistic fidelity. */
export interface QualityReport {
  score: number
  level: QualityLevel
  warnings: string[]
  foregroundCoverage: number
  pathCount: number
  retainedColorCount: number
  removedComponentCount: number
  visualSimilarity: number
  svgComplexity: {
    commandCount: number
    pathDataCharacters: number
    level: 'low' | 'medium' | 'high'
  }
  modelMetadata?: {
    requested: boolean
    provider: string
    modelId?: string | null
    version?: string | null
    architecture?: string | null
    checkpoint?: string | null
    checkpointSha256?: string | null
    fallbackReason?: string | null
  } | null
  inputKind?: string | null
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
  quality?: QualityReport
}

/** Prefer the editable SVG so the workbench shows the exact download artifact. */
export function vectorPreviewUrl(job?: VectorizationJob | null): string | undefined {
  return job?.artifacts.svgUrl ?? job?.artifacts.previewUrl
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
  quality?: {
    score: number
    level: QualityLevel
    warnings?: string[]
    foreground_coverage: number
    path_count: number
    retained_color_count: number
    removed_component_count: number
    visual_similarity: number
    svg_complexity: {
      command_count: number
      path_data_characters: number
      level: 'low' | 'medium' | 'high'
    }
    model_metadata?: {
      requested: boolean
      provider: string
      model_id?: string | null
      version?: string | null
      architecture?: string | null
      checkpoint?: string | null
      checkpoint_sha256?: string | null
      fallback_reason?: string | null
    } | null
    input_kind?: string | null
  } | null
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
    quality: job.quality
      ? {
          score: job.quality.score,
          level: job.quality.level,
          warnings: job.quality.warnings ?? [],
          foregroundCoverage: job.quality.foreground_coverage,
          pathCount: job.quality.path_count,
          retainedColorCount: job.quality.retained_color_count,
          removedComponentCount: job.quality.removed_component_count,
          visualSimilarity: job.quality.visual_similarity,
          svgComplexity: {
            commandCount: job.quality.svg_complexity.command_count,
            pathDataCharacters: job.quality.svg_complexity.path_data_characters,
            level: job.quality.svg_complexity.level,
          },
          modelMetadata: job.quality.model_metadata
            ? {
                requested: job.quality.model_metadata.requested,
                provider: job.quality.model_metadata.provider,
                modelId: job.quality.model_metadata.model_id,
                version: job.quality.model_metadata.version,
                architecture: job.quality.model_metadata.architecture,
                checkpoint: job.quality.model_metadata.checkpoint,
                checkpointSha256: job.quality.model_metadata.checkpoint_sha256,
                fallbackReason: job.quality.model_metadata.fallback_reason,
              }
            : undefined,
          inputKind: job.quality.input_kind,
        }
      : undefined,
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

export async function createVectorization(file: File, options: VectorizationOptions, idempotencyKey: string, signal?: AbortSignal): Promise<VectorizationJob> {
  const body = new FormData()
  body.append('image', file)
  body.append('mode', options.mode)
  body.append('color_count', String(options.colorCount))
  body.append('smoothing', String(options.smoothing / 100))
  body.append('min_component_area', String(options.minimumComponentArea))
  body.append('use_segmentation_model', String(options.useSegmentation))
  const response = await fetch(apiPath('/vectorizations'), {
    method: 'POST',
    body,
    signal,
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  if (!response.ok) throw new Error(await parseError(response))
  return mapJob((await response.json()) as ApiJob)
}

export async function getVectorization(id: string, signal?: AbortSignal): Promise<VectorizationJob> {
  const response = await fetch(apiPath(`/vectorizations/${encodeURIComponent(id)}`), { signal })
  if (!response.ok) throw new Error(await parseError(response))
  return mapJob((await response.json()) as ApiJob)
}
