import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { createVectorization, getVectorization, vectorPreviewUrl } from './api'
import { BatchWorkbench } from './batch'
import { ArtworkPane, Downloads, Header, Inspector, QualityPanel, RecommendationNotice, StatusTimeline, UploadDropzone } from './components'
import { analyzeImageFile } from './recommendation'
import { initialState, workbenchReducer } from './state'

const POLL_INTERVAL_MS = 1_200
const SUBMIT_RETRY_DELAYS_MS = [1_000, 2_500, 5_000]

function isPolling(status?: string): boolean {
  return status === 'queued' || status === 'processing'
}

export default function App() {
  const [state, dispatch] = useReducer(workbenchReducer, initialState)
  const [batchMode, setBatchMode] = useState(false)
  const currentSourceUrl = useRef<string | null>(null)
  // A temporary POST failure can be retried with the same key. After the API
  // confirms a job, a later explicit conversion receives a fresh key.
  const pendingSubmissionKey = useRef<string | null>(null)

  const selectFile = useCallback((file: File) => {
    const sourceUrl = URL.createObjectURL(file)
    if (currentSourceUrl.current) URL.revokeObjectURL(currentSourceUrl.current)
    currentSourceUrl.current = sourceUrl
    pendingSubmissionKey.current = null
    dispatch({ type: 'file-selected', file, sourceUrl })
    void analyzeImageFile(file)
      .then((recommendation) => dispatch({ type: 'recommendation-ready', file, sourceUrl, recommendation }))
      // A file can always be vectorized with the current manual settings if
      // browser-side analysis is unavailable.
      .catch(() => dispatch({ type: 'recommendation-unavailable', file, sourceUrl }))
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
        if ((error as DOMException).name !== 'AbortError') {
          // A transient proxy restart must not turn a running job into a
          // failed conversion. Keep the job identity and try the status call
          // again; the server remains the source of truth.
          dispatch({ type: 'poll-retry-requested' })
        }
      }
    }, POLL_INTERVAL_MS)
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [pollingJob, state.pollRetryAttempt])

  const submit = useCallback(async () => {
    if (!state.file || state.submitting || isPolling(state.job?.status)) return
    dispatch({ type: 'submit-started' })
    const idempotencyKey = pendingSubmissionKey.current ?? crypto.randomUUID()
    pendingSubmissionKey.current = idempotencyKey
    for (let attempt = 0; attempt <= SUBMIT_RETRY_DELAYS_MS.length; attempt += 1) {
      try {
        const job = await createVectorization(state.file, state.options, idempotencyKey)
        pendingSubmissionKey.current = null
        dispatch({ type: 'job-updated', job })
        return
      } catch (error) {
        const message = error instanceof Error ? error.message : 'The upload could not be processed.'
        const transient = /5\d\d|failed to fetch|network/i.test(message)
        if (!transient || attempt === SUBMIT_RETRY_DELAYS_MS.length) {
          dispatch({ type: 'request-failed', error: message })
          return
        }
        await new Promise((resolve) => window.setTimeout(resolve, SUBMIT_RETRY_DELAYS_MS[attempt]))
      }
    }
  }, [state.file, state.job?.status, state.options, state.submitting])

  const reset = useCallback(() => {
    if (currentSourceUrl.current) URL.revokeObjectURL(currentSourceUrl.current)
    currentSourceUrl.current = null
    pendingSubmissionKey.current = null
    dispatch({ type: 'reset' })
  }, [])

  const retry = useCallback(() => {
    if (state.job && isPolling(state.job.status)) {
      dispatch({ type: 'poll-retry-requested' })
      return
    }
    void submit()
  }, [state.job, submit])

  const job = state.job
  // The vector pane must show the same editable artifact offered by Download
  // SVG. The raster preview remains available through the comparison download.
  const previewUrl = vectorPreviewUrl(job)
  const sourceUrl = job?.artifacts.sourceUrl ?? state.sourceUrl
  const processingBusy = state.submitting || isPolling(job?.status)
  const busy = processingBusy || state.recommendationPending
  const failure = state.error ?? (job?.status === 'failed' ? job.error ?? 'The conversion could not be completed. Try adjusting the artwork or settings.' : null)
  return (
    <div className="app-shell" id="workbench">
      <Header onReset={batchMode ? () => setBatchMode(false) : reset} canReset={batchMode || Boolean(state.file || state.job)} batchMode={batchMode} onToggleBatch={() => setBatchMode((current) => !current)} />
      <main>
        {batchMode ? <BatchWorkbench /> : <>
          <section className="intro"><h1>Turn rough pixels into precise paths.</h1><p>VectorForge isolates your artwork, finds its shapes, and exports a clean SVG you can keep editing.</p></section>
          <div className="workbench-layout">
            <div className="workspace">
              <UploadDropzone file={state.file} onFile={selectFile} onError={(error) => dispatch({ type: 'request-failed', error })} disabled={processingBusy} />
              {processingBusy ? <aside className="progress-banner" role="status" aria-live="polite"><strong>{state.submitting ? 'Starting conversion…' : job?.status === 'queued' ? 'Conversion queued…' : 'Converting your artwork…'}</strong><span>{state.submitting ? 'Connecting to the processing service. This can take a few seconds.' : 'Finding shapes and preparing your editable SVG.'}</span></aside> : null}
              {failure ? <div className="error-banner" role="alert"><strong>We couldn’t finish that conversion.</strong><span>{failure}</span>{state.file ? <button className="retry-button" type="button" onClick={retry}>Retry</button> : null}{state.error ? <button type="button" onClick={() => dispatch({ type: 'error-cleared' })} aria-label="Dismiss error">×</button> : null}</div> : null}
              {state.recommendationPending ? <aside className="recommendation" aria-live="polite"><strong>Analyzing new image…</strong><span>Waiting to apply settings for this upload. You can select another image at any time.</span></aside> : state.recommendation ? <RecommendationNotice recommendation={state.recommendation} /> : state.recommendationUnavailable ? <aside className="recommendation" aria-live="polite"><strong>Automatic recommendation unavailable</strong><span>Choose Line art or Illustration manually, then vectorize.</span></aside> : null}
              <div className="artwork-grid"><ArtworkPane title="Original" caption="Your uploaded raster" imageUrl={sourceUrl} emptyText="Your source image will appear here" /><ArtworkPane title="Vector result" caption="Live SVG preview" imageUrl={previewUrl} emptyText={state.recommendationPending ? 'Analyzing your new upload…' : processingBusy ? 'VectorForge is tracing your artwork…' : 'Your editable SVG will appear here'} isVector /></div>
              <StatusTimeline status={job?.status} modelUsed={job?.modelUsed} revectorizeRequired={state.revectorizeRequired} />
              <QualityPanel quality={job?.quality} modelUsed={job?.modelUsed} />
              <Downloads svgUrl={job?.artifacts.svgUrl} comparisonUrl={job?.artifacts.comparisonUrl} />
            </div>
            <Inspector options={state.options} disabled={busy || !state.file} onChange={(options) => { pendingSubmissionKey.current = null; dispatch({ type: 'options-updated', options }) }} onSubmit={submit} />
          </div>
        </>}
      </main>
      <footer>VectorForge works best with clear sketches, logos, and flat-color illustrations.</footer>
    </div>
  )
}
