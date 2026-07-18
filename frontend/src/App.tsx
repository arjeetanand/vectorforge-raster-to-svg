import { useCallback, useEffect, useReducer, useRef } from 'react'
import { createVectorization, getVectorization } from './api'
import { ArtworkPane, Downloads, Header, Inspector, StatusTimeline, UploadDropzone } from './components'
import { initialState, workbenchReducer } from './state'

const POLL_INTERVAL_MS = 1_200

function isPolling(status?: string): boolean {
  return status === 'queued' || status === 'processing'
}

export default function App() {
  const [state, dispatch] = useReducer(workbenchReducer, initialState)
  const currentSourceUrl = useRef<string | null>(null)

  const selectFile = useCallback((file: File) => {
    const sourceUrl = URL.createObjectURL(file)
    if (currentSourceUrl.current) URL.revokeObjectURL(currentSourceUrl.current)
    currentSourceUrl.current = sourceUrl
    dispatch({ type: 'file-selected', file, sourceUrl })
  }, [])

  useEffect(() => () => { if (currentSourceUrl.current) URL.revokeObjectURL(currentSourceUrl.current) }, [])

  const pollingJob = state.job
  useEffect(() => {
    const job = pollingJob
    if (!job || !isPolling(job.status)) return
    const jobId = job.id
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const job = await getVectorization(jobId, controller.signal)
        dispatch({ type: 'job-updated', job })
      } catch (error) {
        if ((error as DOMException).name !== 'AbortError') dispatch({ type: 'request-failed', error: error instanceof Error ? error.message : 'Unable to check conversion progress.' })
      }
    }, POLL_INTERVAL_MS)
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [pollingJob])

  const submit = useCallback(async () => {
    if (!state.file || state.submitting || isPolling(state.job?.status)) return
    dispatch({ type: 'submit-started' })
    try {
      const job = await createVectorization(state.file, state.options)
      dispatch({ type: 'job-updated', job })
    } catch (error) {
      dispatch({ type: 'request-failed', error: error instanceof Error ? error.message : 'The upload could not be processed.' })
    }
  }, [state.file, state.job?.status, state.options, state.submitting])

  const reset = useCallback(() => {
    if (currentSourceUrl.current) URL.revokeObjectURL(currentSourceUrl.current)
    currentSourceUrl.current = null
    dispatch({ type: 'reset' })
  }, [])

  const job = state.job
  const previewUrl = job?.artifacts.previewUrl ?? job?.artifacts.svgUrl
  const sourceUrl = job?.artifacts.sourceUrl ?? state.sourceUrl
  const busy = state.submitting || isPolling(job?.status)
  const failure = state.error ?? (job?.status === 'failed' ? job.error ?? 'The conversion could not be completed. Try adjusting the artwork or settings.' : null)
  return (
    <div className="app-shell" id="workbench">
      <Header onReset={reset} canReset={Boolean(state.file || state.job)} />
      <main>
        <section className="intro"><h1>Turn rough pixels into precise paths.</h1><p>VectorForge isolates your artwork, finds its shapes, and exports a clean SVG you can keep editing.</p></section>
        <div className="workbench-layout">
          <div className="workspace">
            <UploadDropzone file={state.file} onFile={selectFile} onError={(error) => dispatch({ type: 'request-failed', error })} disabled={busy} />
            {failure ? <div className="error-banner" role="alert"><strong>We couldn’t finish that conversion.</strong><span>{failure}</span>{state.file ? <button className="retry-button" type="button" onClick={submit}>Retry</button> : null}{state.error ? <button type="button" onClick={() => dispatch({ type: 'error-cleared' })} aria-label="Dismiss error">×</button> : null}</div> : null}
            <div className="artwork-grid"><ArtworkPane title="Original" caption="Your uploaded raster" imageUrl={sourceUrl} emptyText="Your source image will appear here" /><ArtworkPane title="Vector result" caption="Live SVG preview" imageUrl={previewUrl} emptyText={busy ? 'VectorForge is tracing your artwork…' : 'Your editable SVG will appear here'} isVector /></div>
            <StatusTimeline status={job?.status} modelUsed={job?.modelUsed} />
            <Downloads svgUrl={job?.artifacts.svgUrl} comparisonUrl={job?.artifacts.comparisonUrl} />
          </div>
          <Inspector options={state.options} disabled={busy || !state.file} onChange={(options) => dispatch({ type: 'options-updated', options })} onSubmit={submit} />
        </div>
      </main>
      <footer>VectorForge works best with clear sketches, logos, and flat-color illustrations.</footer>
    </div>
  )
}
