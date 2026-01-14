export type StudyDirection = 'maximize' | 'minimize'

export type TrialState = 'running' | 'complete' | 'pruned' | 'fail'

export interface OptunaStudy {
  id: number
  experiment_id: number
  study_name: string
  direction: StudyDirection
  metric: string
  n_trials: number
  n_trials_target?: number
  status: 'running' | 'completed' | 'failed'
  state?: 'running' | 'completed' | 'failed'
  best_params?: Record<string, unknown>
  best_value?: number
  created_at: string
  completed_at?: string
  datetime_start?: string
  datetime_complete?: string
}

export interface OptunaTrial {
  id: number
  study_id: number
  trial_number: number
  params: Record<string, unknown>
  value?: number
  state: TrialState
  metrics?: Record<string, unknown>
  created_at: string
  completed_at?: string
}

export interface OptunaConfig {
  metric: string
  direction: StudyDirection
  n_trials: number
  search_space: Record<string, unknown>
  enable_pruning?: boolean
  n_jobs?: number
}
