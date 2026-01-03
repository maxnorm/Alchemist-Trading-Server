export interface TradingStatus {
  is_active: boolean
  kill_switch_active: boolean
  circuit_breaker_active: boolean
  active_positions: number
  total_equity: number
  total_balance: number
}

export interface Position {
  id: number
  symbol: string
  order_type: 'BUY' | 'SELL'
  volume: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  opened_at: string
}

export interface CircuitBreakerStatus {
  is_active: boolean
  breaker_type?: string
  trigger_value?: number
  threshold_value?: number
  triggered_at?: string
}
