import { useId, type ChangeEvent, type DragEvent } from 'react'
import type { JobStatus, VectorizationOptions } from './api'
import type { VectorizationRecommendation } from './recommendation'
import { ArrowRightIcon, CheckIcon, DownloadIcon, ImageIcon, SlidersIcon, UploadIcon } from './icons'

const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])

function formatBytes(bytes: number): string {
  if (bytes < 1_000_000) return `${Math.max(1, Math.round(bytes / 1_000))} KB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}

export function Header({ onReset, canReset }: { onReset: () => void; canReset: boolean }) {
  return (
    <header className="app-header">
      <a className="brand" href="#workbench" aria-label="VectorForge home">
        <span className="brand-mark"><ArrowRightIcon size={17} /></span>
        <span>VectorForge</span>
      </a>
      <p className="header-note">Raster → editable vector</p>
      <button className="text-button" type="button" disabled={!canReset} onClick={onReset}>Start over</button>
    </header>
  )
}

interface UploadDropzoneProps {
  file: File | null
  onFile: (file: File) => void
  onError: (message: string) => void
  disabled: boolean
}

export function UploadDropzone({ file, onFile, onError, disabled }: UploadDropzoneProps) {
  const inputId = useId()
  const choose = (candidate?: File) => {
    if (!candidate || disabled) return
    if (!ACCEPTED_TYPES.has(candidate.type)) {
      onError('Choose a PNG, JPEG, or WebP image.')
      return
    }
    if (candidate.size > 10_000_000) {
      onError('This image is larger than the 10 MB upload limit.')
      return
    }
    onFile(candidate)
  }
  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    choose(event.currentTarget.files?.[0])
    // Let a user choose the same local file again after replacing it or after
    // a failed recommendation; browsers otherwise suppress a second change.
    event.currentTarget.value = ''
  }
  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    choose(event.dataTransfer.files[0])
  }
  return (
    <label className={`dropzone${disabled ? ' is-disabled' : ''}`} htmlFor={inputId} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
      <input id={inputId} type="file" accept="image/png,image/jpeg,image/webp" onChange={onChange} disabled={disabled} />
      {file ? (
        <><span className="upload-icon"><ImageIcon /></span><strong>{file.name}</strong><span>{formatBytes(file.size)} · choose another image</span></>
      ) : (
        <><span className="upload-icon"><UploadIcon /></span><strong>Drop an image here</strong><span>or browse your device · PNG, JPEG, WebP · up to 10 MB</span></>
      )}
    </label>
  )
}

interface InspectorProps {
  options: VectorizationOptions
  disabled: boolean
  onChange: (options: Partial<VectorizationOptions>) => void
  onSubmit: () => void
}

export function Inspector({ options, disabled, onChange, onSubmit }: InspectorProps) {
  return (
    <aside className="inspector" aria-label="Vectorization controls">
      <div className="panel-heading"><span className="panel-icon"><SlidersIcon size={17} /></span><div><h2>Vectorization</h2><p>Fine-tune the result before converting.</p></div></div>
      <fieldset className="field-group">
        <legend>Artwork type</legend>
        <div className="segmented-control">
          {(['line-art', 'illustration'] as const).map((mode) => <button key={mode} type="button" className={options.mode === mode ? 'is-selected' : ''} onClick={() => onChange({ mode })} disabled={disabled}>{mode === 'line-art' ? 'Line art' : 'Illustration'}</button>)}
        </div>
      </fieldset>
      <RangeField label="Color layers" value={options.colorCount} min={2} max={16} disabled={disabled} onChange={(colorCount) => onChange({ colorCount })} hint={options.mode === 'line-art' ? 'Used only for preview color matching.' : 'Number of flat colors to preserve.'} />
      <RangeField label="Path smoothing" value={options.smoothing} min={0} max={100} disabled={disabled} onChange={(smoothing) => onChange({ smoothing })} hint="Balances crisp corners with fluid curves." />
      <label className="number-field"><span><strong>Minimum detail area</strong><small>Remove tiny isolated components.</small></span><input type="number" min="1" max="10000" value={options.minimumComponentArea} disabled={disabled} onChange={(event) => onChange({ minimumComponentArea: Number(event.currentTarget.value) || 1 })} /><em>px²</em></label>
      <label className="switch-field"><span><strong>Foreground segmentation</strong><small>Separate artwork from noisy backgrounds.</small></span><input className="sr-only" type="checkbox" checked={options.useSegmentation} disabled={disabled} onChange={(event) => onChange({ useSegmentation: event.currentTarget.checked })} /><i aria-hidden="true" /></label>
      <button type="button" className="primary-button" disabled={disabled} onClick={onSubmit}><span>Vectorize image</span><ArrowRightIcon size={17} /></button>
    </aside>
  )
}

export function RecommendationNotice({ recommendation }: { recommendation: VectorizationRecommendation }) {
  return <aside className="recommendation" aria-live="polite"><strong>Auto-selected {recommendation.mode === 'line-art' ? 'Line art' : 'Illustration'}</strong><span>{recommendation.message}</span><small>{recommendation.confidence === 'high' ? 'High-confidence recommendation' : 'Starting recommendation — adjust settings if needed.'}</small></aside>
}

function RangeField({ label, value, min, max, hint, disabled, onChange }: { label: string; value: number; min: number; max: number; hint: string; disabled: boolean; onChange: (value: number) => void }) {
  return <label className="range-field"><span><strong>{label}</strong><output>{value}{label === 'Path smoothing' ? '%' : ''}</output></span><input type="range" min={min} max={max} value={value} disabled={disabled} onChange={(event) => onChange(Number(event.currentTarget.value))} /><small>{hint}</small></label>
}

export function ArtworkPane({ title, caption, imageUrl, emptyText, isVector = false }: { title: string; caption: string; imageUrl?: string | null; emptyText: string; isVector?: boolean }) {
  return (
    <section className="artwork-pane" aria-label={title}>
      <div className="pane-title"><div><h2>{title}</h2><p>{caption}</p></div>{isVector ? <span className="vector-label">SVG</span> : null}</div>
      <div className={`artwork-surface${imageUrl ? '' : ' is-empty'}`}>
        {imageUrl ? <img src={imageUrl} alt={isVector ? 'Vectorized image preview' : 'Selected source artwork'} /> : <div className="empty-artwork"><ImageIcon size={28} /><span>{emptyText}</span></div>}
      </div>
    </section>
  )
}

const statusSteps: { status: JobStatus; title: string; note: string }[] = [
  { status: 'queued', title: 'Queued', note: 'Job is ready to start' },
  { status: 'processing', title: 'Processing', note: 'Finding shapes and colors' },
  { status: 'completed', title: 'Ready', note: 'Editable SVG is available' },
]

export function StatusTimeline({ status, modelUsed, revectorizeRequired = false }: { status?: JobStatus; modelUsed?: string; revectorizeRequired?: boolean }) {
  const activeIndex = status ? statusSteps.findIndex((step) => step.status === status) : -1
  const heading = revectorizeRequired ? 'Settings updated' : status === 'completed' ? 'Your vector is ready' : status === 'failed' ? 'Conversion needs attention' : status ? 'Creating your vector' : 'Ready when you are'
  const detail = revectorizeRequired ? 'The previous result was cleared. Select Vectorize image to create a new SVG with these settings.' : modelUsed ? `Foreground mask: ${modelUsed}` : 'Upload artwork, adjust the settings, and start a conversion.'
  return <section className="status-section" aria-live="polite" aria-atomic="true"><div className="status-heading"><div><h2>{heading}</h2><p>{detail}</p></div>{status === 'completed' ? <span className="ready-dot"><CheckIcon size={15} /> Complete</span> : null}</div>{status === 'failed' ? null : <ol className="timeline">{statusSteps.map((step, index) => <li key={step.status} className={index <= activeIndex ? 'is-active' : ''}><span>{index < activeIndex ? <CheckIcon size={14} /> : index + 1}</span><div><strong>{step.title}</strong><small>{step.note}</small></div></li>)}</ol>}</section>
}

export function Downloads({ svgUrl, comparisonUrl }: { svgUrl?: string; comparisonUrl?: string }) {
  if (!svgUrl && !comparisonUrl) return null
  return <div className="download-row" aria-label="Download outputs">
    {svgUrl ? <a className="download-button is-primary" href={svgUrl} download><DownloadIcon size={16} /> Download SVG</a> : null}
    {comparisonUrl ? <a className="download-button" href={comparisonUrl} download><DownloadIcon size={16} /> Comparison PNG</a> : null}
  </div>
}
