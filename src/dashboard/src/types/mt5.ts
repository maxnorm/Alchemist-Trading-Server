export type AccountType = 'demo' | 'live'

export type ConnectionStatusType = 'connected' | 'disconnected' | 'paused'

export interface MT5Account {
  id: number
  account_login: number
  account_type: AccountType
  broker_name?: string
  broker_server?: string
  account_currency?: string
  account_leverage?: number
  account_name?: string
  balance?: number
  equity?: number
  profit?: number
  is_active: boolean
  last_seen_at?: string
  created_at: string
  updated_at?: string
  // Computed fields from API
  connection_status?: ConnectionStatusType
  current_model_id?: number
  current_model_version?: string
  trading_enabled?: boolean
  // Connection details from EA
  terminal_id?: number
  ea_version?: string
  connection_ip?: string
  connected_at?: string
}

export interface MT5AccountSecret extends MT5Account {
  // Legacy fields - no longer used for Python API accounts
  auth_token?: string
  server_host?: string
  server_port?: number
}

export interface MT5AccountCreatePayload {
  account_login: number
  account_type: AccountType
  broker_name?: string
  broker_server?: string
  account_currency?: string
  account_leverage?: number
  account_name?: string
  mt5_password?: string  // Optional - required for Python API connection, leave empty for ZeroMQ
  mt5_server?: string     // Optional - required for Python API connection, leave empty for ZeroMQ
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
