export type ModelStage = 'training' | 'staging' | 'paper' | 'production' | 'archived'

export interface Model {
  id: number
  experiment_id: number
  name: string
  version: string
  model_type?: string
  mlflow_run_id?: string
  model_path?: string
  stage: ModelStage
  promoted_at?: string
  promoted_by?: string
  performance_metrics?: Record<string, unknown>
  paper_trading_results?: PaperTradingResults
  created_at: string
  updated_at?: string
}

export interface ModelMetrics {
  sharpe_ratio?: number
  win_rate?: number
  total_trades?: number
  total_pnl?: number
  max_drawdown?: number
}

export interface PaperSession {
  id: number
  model_id: number
  status: 'running' | 'completed' | 'stopped'
  start_balance: number
  current_balance: number
  total_trades: number
  winning_trades: number
  pnl: number
  sharpe_ratio?: number
  max_drawdown?: number
  started_at: string
  ended_at?: string
}

export interface ValidationResult {
  passed: boolean
  checks: Record<string, boolean>
  metrics: Record<string, number>
  messages: string[]
}

export interface PaperTradingResults {
  sharpe_ratio?: number
  win_rate?: number
  total_trades?: number
  max_drawdown?: number
  pnl?: number
  days_traded?: number
}