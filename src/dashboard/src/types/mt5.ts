export type AccountType = 'demo' | 'live'

export interface MT5Account {
  id: number
  account_login: number
  account_type: AccountType
  broker_name?: string
  broker_server?: string
  account_currency?: string
  account_leverage?: number
  account_name?: string
  is_active: boolean
  last_seen_at?: string
  created_at: string
  updated_at?: string
}

export interface ModelAssignment {
  id: number
  account_id: number
  model_id: number
  trading_mode: 'paper' | 'live'
  is_active: boolean
  assigned_at: string
  assigned_by?: number
  deactivated_at?: string
  notes?: string
}

export interface ConnectionStatus {
  account_id: number
  is_connected: boolean
  connected_at?: string
  disconnected_at?: string
  ea_version?: string
  connection_ip?: string
}
