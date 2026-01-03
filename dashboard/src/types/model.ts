export type ModelStage = 'training' | 'staging' | 'paper' | 'production' | 'archived'

export interface Model {
  id: number
  experiment_id: number
  name: string
  version: string
  mlflow_run_id?: string
  model_path?: string
  stage: ModelStage
  promoted_at?: string
  promoted_by?: string
  performance_metrics?: Record<string, any>
  paper_trading_results?: Record<string, any>
  created_at: string
}

export interface ModelMetrics {
  sharpe_ratio?: number
  win_rate?: number
  total_trades?: number
  total_pnl?: number
  max_drawdown?: number
}
