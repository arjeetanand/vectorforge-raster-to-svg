import type { VectorizationJob, VectorizationOptions } from './api'
import type { VectorizationRecommendation } from './recommendation'

export interface WorkbenchState {
  file: File | null
  sourceUrl: string | null
  options: VectorizationOptions
  job: VectorizationJob | null
  submitting: boolean
  error: string | null
  recommendation: VectorizationRecommendation | null
  revectorizeRequired: boolean
  pollRetryAttempt: number
}

export const defaultOptions: VectorizationOptions = {
  mode: 'line-art',
  colorCount: 6,
  smoothing: 45,
  minimumComponentArea: 40,
  useSegmentation: true,
}

export const initialState: WorkbenchState = {
  file: null,
  sourceUrl: null,
  options: defaultOptions,
  job: null,
  submitting: false,
  error: null,
  recommendation: null,
  revectorizeRequired: false,
  pollRetryAttempt: 0,
}

export type WorkbenchAction =
  | { type: 'file-selected'; file: File; sourceUrl: string }
  | { type: 'recommendation-ready'; file: File; sourceUrl: string; recommendation: VectorizationRecommendation }
  | { type: 'options-updated'; options: Partial<VectorizationOptions> }
  | { type: 'submit-started' }
  | { type: 'job-updated'; job: VectorizationJob }
  | { type: 'request-failed'; error: string }
  | { type: 'poll-retry-requested' }
  | { type: 'error-cleared' }
  | { type: 'reset' }

export function workbenchReducer(state: WorkbenchState, action: WorkbenchAction): WorkbenchState {
  switch (action.type) {
    case 'file-selected':
      return { ...state, file: action.file, sourceUrl: action.sourceUrl, recommendation: null, job: null, error: null, revectorizeRequired: false, pollRetryAttempt: 0 }
    case 'recommendation-ready':
      // Image analysis is asynchronous. Ignore a result for an image that the
      // user has already replaced, so it cannot restore stale settings/results.
      if (state.file !== action.file || state.sourceUrl !== action.sourceUrl) return state
      return { ...state, options: action.recommendation.options, recommendation: action.recommendation }
    case 'options-updated': {
      const options = { ...state.options, ...action.options }
      const unchanged = options.mode === state.options.mode
        && options.colorCount === state.options.colorCount
        && options.smoothing === state.options.smoothing
        && options.minimumComponentArea === state.options.minimumComponentArea
        && options.useSegmentation === state.options.useSegmentation
      if (unchanged) return state
      // Options are part of the server job payload. Never leave a completed
      // result or download visible once the user has changed that payload.
      return { ...state, options, recommendation: null, job: null, error: null, revectorizeRequired: Boolean(state.job) }
    }
    case 'submit-started':
      return { ...state, submitting: true, job: null, error: null, revectorizeRequired: false, pollRetryAttempt: 0 }
    case 'job-updated':
      return { ...state, job: action.job, submitting: false, error: null, revectorizeRequired: false }
    case 'request-failed':
      return { ...state, submitting: false, error: action.error }
    case 'poll-retry-requested':
      // Keep the server job identity and restart the polling effect. A fresh
      // upload would duplicate work when only a status request failed.
      return { ...state, error: null, pollRetryAttempt: state.pollRetryAttempt + 1 }
    case 'error-cleared':
      return { ...state, error: null }
    case 'reset':
      return { ...initialState }
  }
}
