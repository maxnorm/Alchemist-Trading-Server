export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export const API_ENDPOINTS = {
  features: '/api/v1/features',
  experiments: '/api/v1/experiments',
  models: '/api/v1/models',
  trading: '/api/v1/trading',
  mt5Accounts: '/api/v1/mt5-accounts',
  performance: '/api/v1/performance',
  optuna: '/api/v1/optuna',
} as const


export const MODEL_STAGES: Record<string, { label: string; color: string }> = {
  training: { label: 'Training', color: 'bg-blue-500' },
  staging: { label: 'Staging', color: 'bg-yellow-500' },
  paper: { label: 'Paper Trading', color: 'bg-purple-500' },
  production: { label: 'Production', color: 'bg-green-500' },
  archived: { label: 'Archived', color: 'bg-gray-500' },
}

export const EXPERIMENT_STATUSES: Record<string, { label: string; color: string }> = {
  created: { label: 'Created', color: 'bg-gray-500' },
  training: { label: 'Training', color: 'bg-blue-500' },
  completed: { label: 'Completed', color: 'bg-green-500' },
  failed: { label: 'Failed', color: 'bg-red-500' },
  paused: { label: 'Paused', color: 'bg-yellow-500' },
}
