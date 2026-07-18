import type { VectorizationJob, VectorizationOptions } from './api'

export interface WorkbenchState {
  file: File | null
  sourceUrl: string | null
  options: VectorizationOptions
  job: VectorizationJob | null
  submitting: boolean
  error: string | null
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
}

export type WorkbenchAction =
  | { type: 'file-selected'; file: File; sourceUrl: string }
  | { type: 'options-updated'; options: Partial<VectorizationOptions> }
  | { type: 'submit-started' }
  | { type: 'job-updated'; job: VectorizationJob }
  | { type: 'request-failed'; error: string }
  | { type: 'error-cleared' }
  | { type: 'reset' }

export function workbenchReducer(state: WorkbenchState, action: WorkbenchAction): WorkbenchState {
  switch (action.type) {
    case 'file-selected':
      return { ...state, file: action.file, sourceUrl: action.sourceUrl, job: null, error: null }
    case 'options-updated':
      return { ...state, options: { ...state.options, ...action.options } }
    case 'submit-started':
      return { ...state, submitting: true, job: null, error: null }
    case 'job-updated':
      return { ...state, job: action.job, submitting: false, error: null }
    case 'request-failed':
      return { ...state, submitting: false, error: action.error }
    case 'error-cleared':
      return { ...state, error: null }
    case 'reset':
      return { ...initialState }
  }
}
