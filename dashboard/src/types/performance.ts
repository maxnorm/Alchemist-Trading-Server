export interface PortfolioMetrics {
  total_pnl: number
  total_pnl_pct: number
  sharpe_ratio: number
  max_drawdown: number
  max_drawdown_pct: number
  win_rate: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  profit_factor: number
  expectancy: number
}

export interface ModelMetrics {
  model_id: number
  total_pnl: number
  total_pnl_pct: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  profit_factor: number
  avg_trade_duration: number
}

export interface EquityPoint {
  timestamp: string
  equity: number
  balance: number
  drawdown_pct: number
  unrealized_pnl?: number
}

export interface Trade {
  id: number
  symbol: string
  order_type: 'BUY' | 'SELL'
  entry_price: number
  exit_price?: number
  volume: number
  pnl?: number
  pnl_pct?: number
  entry_time: string
  exit_time?: string
  status: 'OPEN' | 'CLOSED'
}

export interface PerformanceBreakdown {
  period: string
  pnl: number
  trades: number
  win_rate: number
}