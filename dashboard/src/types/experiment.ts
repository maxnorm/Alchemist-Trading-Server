export type TrainingMode = 'live' | 'historical'

export type ExperimentStatus = 'created' | 'training' | 'completed' | 'failed' | 'paused'

export interface Experiment {
  id: number
  name: string
  description?: string
  features: string[]
  currency_pairs: string[]
  training_mode: TrainingMode
  hyperparameters: Record<string, any>
  status: ExperimentStatus
  mlflow_run_id?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface CreateExperimentDto {
  name: string
  description?: string
  features: string[]
  currency_pairs: string[]
  training_mode: TrainingMode
  hyperparameters: Record<string, any>
}

export interface ExperimentProgress {
  experiment_id: number
  step: number
  episode: number
  loss: number
  reward: number
  sharpe_ratio?: number
  timestamp: string
}
