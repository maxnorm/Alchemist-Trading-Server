// Use relative paths when behind gateway, absolute for dev
const getBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL
  // If env URL is explicitly set (including empty string), always use it (respects docker-compose configuration)
  if (envUrl !== undefined) {
    // Empty string means use relative paths (endpoints already include /api/v1/)
    // If env URL is relative (starts with /), use it as-is for gateway
    // If absolute, use it directly
    return envUrl
  }
  // Fallback: In development, check if we're accessing via gateway (port 80) or directly (port 8000)
  const isGateway = window.location.port === '' || window.location.port === '80'
  return isGateway ? '' : 'http://localhost:8000'
}

const getWsUrl = () => {
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl) {
    // If env URL is relative (starts with /), make it absolute
    if (envUrl.startsWith('/')) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${protocol}//${window.location.host}${envUrl}`
    }
    return envUrl
  }
  // Use same protocol as current page
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return window.location.origin.includes('localhost') 
    ? 'ws://localhost:8000' 
    : `${protocol}//${window.location.host}/ws`
}

export const API_BASE_URL = getBaseUrl()
export const WS_BASE_URL = getWsUrl()

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
