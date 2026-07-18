import { useCallback, useEffect, useId, useRef, useState } from 'react'
import {
  ApiRequestError,
  createVectorizationBatch,
  getVectorizationBatch,
  getVectorizationPresets,
  retryFailedBatch,
  vectorizationBatchArtifactUrl,
  type VectorizationBatch,
  type VectorizationJob,
  type VectorizationOptions,
  type VectorizationPreset,
} from './api'
import { ArrowRightIcon, CheckIcon, DownloadIcon, UploadIcon } from './icons'
import { defaultOptions } from './state'

const MAX_IMAGE_BYTES = 10_000_000
const MAX_ARCHIVE_BYTES = 50_000_000
const MAX_FILES = 100
const POLL_INTERVAL_MS = 1_200
const RETRY_DELAYS_MS = [1_000, 2_500, 5_000]
const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])

function isBatchActive(batch?: VectorizationBatch | null): boolean {
  return batch?.status === 'queued' || batch?.status === 'processing'
}

function isTransient(error: unknown): boolean {
  return /5\d\d|failed to fetch|network/i.test(error instanceof Error ? error.message : String(error))
}

function batchErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError && error.status === 404) {
    return 'The running API service does not include batch conversion. Rebuild and recreate the api, worker, beat, and frontend containers, then refresh this page.'
  }
  return error instanceof Error ? error.message : 'The batch could not be submitted.'
}

function formatBytes(bytes: number): string {
  if (bytes < 1_000_000) return `${Math.max(1, Math.round(bytes / 1_000))} KB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}

function statusLabel(status: VectorizationJob['status']): string {
  return status === 'completed' ? 'Ready' : status === 'failed' ? 'Needs attention' : status === 'processing' ? 'Converting' : 'Queued'
}

interface BatchWorkbenchProps {
  onReset?: () => void
}

export function BatchWorkbench({ onReset }: BatchWorkbenchProps) {
  const imageInputId = useId()
  const archiveInputId = useId()
  const pendingKey = useRef<string | null>(null)
  const [images, setImages] = useState<File[]>([])
  const [archive, setArchive] = useState<File | null>(null)
  const [options, setOptions] = useState<VectorizationOptions>({ ...defaultOptions })
  const [presets, setPresets] = useState<VectorizationPreset[]>([])
  const [selectedPreset, setSelectedPreset] = useState('')
  const [presetError, setPresetError] = useState<string | null>(null)
  const [batch, setBatch] = useState<VectorizationBatch | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [pollAttempt, setPollAttempt] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void getVectorizationPresets(controller.signal)
      .then(setPresets)
      .catch((reason: unknown) => {
        if ((reason as DOMException).name !== 'AbortError') setPresetError('Presets are unavailable; use the manual options below.')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!batch || !isBatchActive(batch)) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void getVectorizationBatch(batch.id, controller.signal)
        .then((next) => {
          setBatch(next)
          setError(null)
        })
        .catch((reason: unknown) => {
          if ((reason as DOMException).name !== 'AbortError') {
            setError('The batch status could not be refreshed. Retrying…')
            setPollAttempt((attempt) => attempt + 1)
          }
        })
    }, POLL_INTERVAL_MS)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [batch, pollAttempt])

  const selectImages = useCallback((candidates: File[]) => {
    const invalidType = candidates.find((file) => !ACCEPTED_TYPES.has(file.type))
    if (invalidType) {
      setError('Choose PNG, JPEG, or WebP images only.')
      return
    }
    const oversized = candidates.find((file) => file.size > MAX_IMAGE_BYTES)
    if (oversized) {
      setError(`${oversized.name} is larger than the 10 MB image limit.`)
      return
    }
    if (candidates.length > MAX_FILES) {
      setError(`A batch may contain at most ${MAX_FILES} images.`)
      return
    }
    setArchive(null)
    setImages(candidates)
    setError(null)
    setBatch(null)
    pendingKey.current = null
  }, [])

  const selectArchive = useCallback((candidate?: File) => {
    if (!candidate) return
    if (candidate.size > MAX_ARCHIVE_BYTES) {
      setError('ZIP archives are limited to 50 MB.')
      return
    }
    if (!candidate.name.toLowerCase().endsWith('.zip') && candidate.type !== 'application/zip') {
      setError('Choose a ZIP archive.')
      return
    }
    setArchive(candidate)
    setImages([])
    setError(null)
    setBatch(null)
    pendingKey.current = null
  }, [])

  const submit = useCallback(async () => {
    if ((!images.length && !archive) || submitting || isBatchActive(batch)) return
    setSubmitting(true)
    setError(null)
    const key = pendingKey.current ?? crypto.randomUUID()
    pendingKey.current = key
    for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt += 1) {
      try {
        const created = await createVectorizationBatch(images, archive, options, key)
        pendingKey.current = null
        setBatch(created)
        setSubmitting(false)
        setPollAttempt(0)
        return
      } catch (reason) {
        if (!isTransient(reason) || attempt === RETRY_DELAYS_MS.length) {
          setSubmitting(false)
          setError(batchErrorMessage(reason))
          return
        }
        await new Promise((resolve) => window.setTimeout(resolve, RETRY_DELAYS_MS[attempt]))
      }
    }
  }, [archive, batch, images, options, submitting])

  const retryFailed = useCallback(async () => {
    if (!batch || batch.failedCount === 0 || retrying) return
    setRetrying(true)
    setError(null)
    try {
      setBatch(await retryFailedBatch(batch.id))
      setPollAttempt(0)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Failed files could not be queued again.')
    } finally {
      setRetrying(false)
    }
  }, [batch, retrying])

  const clear = useCallback(() => {
    setImages([])
    setArchive(null)
    setBatch(null)
    setError(null)
    setSelectedPreset('')
    pendingKey.current = null
    onReset?.()
  }, [onReset])

  const choosePreset = (id: string) => {
    setSelectedPreset(id)
    const preset = presets.find((candidate) => candidate.id === id)
    if (preset) setOptions({ ...preset.options })
  }

  const busy = submitting || retrying || isBatchActive(batch)
  const hasInput = images.length > 0 || Boolean(archive)
  return (
    <section className="batch-workspace" aria-labelledby="batch-title">
      <div className="batch-heading">
        <div>
          <p className="eyebrow">Batch conversion</p>
          <h1 id="batch-title">Convert a whole folder in one pass.</h1>
          <p>Upload up to 100 supported artwork files or one ZIP archive. Each file keeps its own status and downloadable SVG.</p>
        </div>
        <button type="button" className="text-button" onClick={clear}>Clear batch</button>
      </div>

      <div className="batch-input-grid">
        <label className={`batch-dropzone${busy || archive ? ' is-disabled' : ''}`} htmlFor={imageInputId}>
          <input id={imageInputId} type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={busy || Boolean(archive)} onChange={(event) => { selectImages(Array.from(event.currentTarget.files ?? [])); event.currentTarget.value = '' }} />
          <span className="upload-icon"><UploadIcon /></span>
          <strong>Select images</strong>
          <span>PNG, JPEG, or WebP · up to 100 files</span>
        </label>
        <label className={`batch-dropzone${busy || images.length ? ' is-disabled' : ''}`} htmlFor={archiveInputId}>
          <input id={archiveInputId} type="file" accept=".zip,application/zip" disabled={busy || images.length > 0} onChange={(event) => { selectArchive(event.currentTarget.files?.[0]); event.currentTarget.value = '' }} />
          <span className="upload-icon"><UploadIcon /></span>
          <strong>Select a ZIP archive</strong>
          <span>One archive · up to 50 MB</span>
        </label>
      </div>

      {images.length || archive ? <div className="batch-selection" aria-live="polite">
        <div className="batch-selection-heading"><strong>{archive ? archive.name : `${images.length} image${images.length === 1 ? '' : 's'} selected`}</strong><span>{archive ? formatBytes(archive.size) : 'Ready to process'}</span></div>
        {images.length ? <ul className="batch-file-list">{images.map((file, index) => <li key={`${file.name}-${file.lastModified}-${index}`}><span>{file.name}</span><small>{formatBytes(file.size)}</small><button type="button" onClick={() => setImages((current) => current.filter((_, itemIndex) => itemIndex !== index))} disabled={busy} aria-label={`Remove ${file.name}`}>×</button></li>)}</ul> : null}
      </div> : null}

      <div className="batch-controls">
        <label className="batch-preset"><span><strong>Conversion preset</strong><small>Start with a workflow profile, then adjust settings.</small></span><select value={selectedPreset} onChange={(event) => choosePreset(event.currentTarget.value)} disabled={busy || presets.length === 0}><option value="">Manual settings</option>{presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}</select></label>
        {presetError ? <p className="batch-muted">{presetError}</p> : null}
        <div className="batch-option-grid">
          <label><span>Artwork type</span><select value={options.mode} disabled={busy} onChange={(event) => setOptions((current) => ({ ...current, mode: event.currentTarget.value as VectorizationOptions['mode'] }))}><option value="line-art">Line art</option><option value="illustration">Illustration</option></select></label>
          <label><span>Color layers</span><input type="number" min="2" max="16" value={options.colorCount} disabled={busy} onChange={(event) => setOptions((current) => ({ ...current, colorCount: Number(event.currentTarget.value) || 2 }))} /></label>
          <label><span>Smoothing (%)</span><input type="number" min="0" max="100" value={options.smoothing} disabled={busy} onChange={(event) => setOptions((current) => ({ ...current, smoothing: Number(event.currentTarget.value) || 0 }))} /></label>
          <label><span>Minimum detail area</span><input type="number" min="1" max="100000" value={options.minimumComponentArea} disabled={busy} onChange={(event) => setOptions((current) => ({ ...current, minimumComponentArea: Number(event.currentTarget.value) || 1 }))} /></label>
        </div>
        <label className="batch-switch"><span><strong>Foreground segmentation</strong><small>Use the optional model for noisy backgrounds; OpenCV remains the fallback.</small></span><input type="checkbox" checked={options.useSegmentation} disabled={busy} onChange={(event) => setOptions((current) => ({ ...current, useSegmentation: event.currentTarget.checked }))} /></label>
      </div>

      {error ? <div className="error-banner" role="alert"><strong>Batch update</strong><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss batch error">×</button></div> : null}
      <div className="batch-actions"><button type="button" className="primary-button" disabled={!hasInput || busy} onClick={() => void submit()}><span>{submitting ? 'Submitting batch…' : isBatchActive(batch) ? 'Batch in progress…' : 'Start batch conversion'}</span><ArrowRightIcon size={17} /></button>{batch?.failedCount ? <button type="button" className="secondary-button" disabled={busy} onClick={() => void retryFailed()}>{retrying ? 'Retrying…' : `Retry ${batch.failedCount} failed`}</button> : null}</div>

      {batch ? <section className="batch-results" aria-labelledby="batch-results-title" aria-live="polite">
        <div className="batch-results-heading"><div><h2 id="batch-results-title">Batch status</h2><p>{batch.completedCount} of {batch.totalCount} ready · {batch.failedCount} failed</p></div><span className={`batch-status is-${batch.status}`}>{batch.status === 'partial' ? 'Needs review' : batch.status}</span></div>
        <ol className="batch-items">{batch.items.map((item) => <li key={item.id} className={`batch-item is-${item.status}`}><span className="batch-item-icon">{item.status === 'completed' ? <CheckIcon size={14} /> : item.status === 'failed' ? '!' : '…'}</span><div><strong>{item.sourceFilename ?? item.id}</strong><small>{statusLabel(item.status)}{item.error ? ` · ${item.error}` : ''}</small></div>{item.artifacts.svgUrl ? <a className="download-button" href={item.artifacts.svgUrl} download><DownloadIcon size={14} /> SVG</a> : null}</li>)}</ol>
        {!isBatchActive(batch) ? <div className="batch-downloads" aria-label="Batch downloads"><a className="download-button is-primary" href={vectorizationBatchArtifactUrl(batch.id, 'results.zip')} download><DownloadIcon size={14} /> Results ZIP</a><a className="download-button" href={vectorizationBatchArtifactUrl(batch.id, 'report.csv')} download>CSV report</a><a className="download-button" href={vectorizationBatchArtifactUrl(batch.id, 'report.json')} download>JSON report</a></div> : null}
      </section> : null}
    </section>
  )
}
