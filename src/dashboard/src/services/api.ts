import axios, { AxiosInstance, AxiosError } from 'axios'
import { API_BASE_URL, API_ENDPOINTS } from '@/utils/constants'
import type { Experiment, CreateExperimentDto } from '@/types/experiment'
import type { Feature, FeatureFilters } from '@/types/feature'
import type { Model, ModelStage } from '@/types/model'
import type { TradingStatus, CircuitBreakerStatus } from '@/types/trading'
import type { MT5Account, MT5AccountCreatePayload, ModelAssignment } from '@/types/mt5'
import type { PortfolioMetrics, ModelMetrics, EquityPoint, Trade, ModelStatistics, ModelComparison } from '@/types/performance'
import type { OptunaStudy, OptunaTrial, OptunaConfig } from '@/types/optuna'
import type { PaperSession, ValidationResult } from '@/types/model'
import type { PerformanceBreakdown } from '@/types/performance'

export class ApiClient {
  private client: AxiosInstance
  private getToken: (() => Promise<string | null>) | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    })

    // Request interceptor - add Clerk token
    this.client.interceptors.request.use(
      async (config) => {
        // Get token from Clerk if token getter is set
        if (this.getToken) {
          const token = await this.getToken()
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
          }
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Token expired or invalid - redirect to sign-in
          if (window.location.pathname !== '/sign-in') {
            window.location.href = '/sign-in'
          }
        } else if (error.response) {
          // Server responded with error
          const errorData = error.response.data as { detail?: string } | undefined
          const message = errorData?.detail || error.message
          return Promise.reject(new Error(message))
        } else if (error.request) {
          // Request made but no response
          return Promise.reject(new Error('Network error: Could not reach server'))
        } else {
          // Something else happened
          return Promise.reject(error)
        }
      }
    )
  }

  // Method to set token getter (called from useClerkApi hook)
  setTokenGetter(getToken: () => Promise<string | null>) {
    this.getToken = getToken
  }

  // Features
  async getFeatures(filters?: FeatureFilters): Promise<Feature[]> {
    const response = await this.client.get<{ features: Feature[]; total: number }>(API_ENDPOINTS.features, { params: filters })
    // API returns { features: [...], total: number }, extract the features array
    if (response.data && response.data.features && Array.isArray(response.data.features)) {
      // Map is_available from API to available for frontend
      return response.data.features.map(f => ({
        ...f,
        available: (f as any).is_available ?? true
      }))
    }
    // Fallback: if response.data is already an array (backward compatibility)
    if (Array.isArray(response.data)) {
      return response.data.map(f => ({
        ...f,
        available: (f as any).is_available ?? f.available ?? true
      }))
    }
    return []
  }

  async getFeature(id: number): Promise<Feature> {
    const response = await this.client.get<Feature>(`${API_ENDPOINTS.features}/${id}`)
    return response.data
  }

  // Experiments
  async getExperiments(): Promise<Experiment[]> {
    const response = await this.client.get<Experiment[]>(API_ENDPOINTS.experiments)
    return Array.isArray(response.data) ? response.data : []
  }

  async getExperiment(id: number): Promise<Experiment> {
    const response = await this.client.get<Experiment>(`${API_ENDPOINTS.experiments}/${id}`)
    return response.data
  }

  async createExperiment(data: CreateExperimentDto): Promise<Experiment> {
    const response = await this.client.post<Experiment>(API_ENDPOINTS.experiments, data)
    return response.data
  }

  async startExperiment(id: number): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.experiments}/${id}/start`)
  }

  async stopExperiment(id: number): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.experiments}/${id}/stop`)
  }

  async cloneExperiment(id: number): Promise<Experiment> {
    const response = await this.client.post<Experiment>(`${API_ENDPOINTS.experiments}/${id}/clone`)
    return response.data
  }

  async deleteExperiment(id: number): Promise<void> {
    await this.client.delete(`${API_ENDPOINTS.experiments}/${id}`)
  }

  // Optuna
  async startOptunaSearch(experimentId: number, config: OptunaConfig): Promise<OptunaStudy> {
    const response = await this.client.post<OptunaStudy>(
      `${API_ENDPOINTS.experiments}/${experimentId}/optuna/start`,
      config
    )
    return response.data
  }

  async getOptunaStatus(experimentId: number): Promise<OptunaStudy> {
    const response = await this.client.get<OptunaStudy>(
      `${API_ENDPOINTS.experiments}/${experimentId}/optuna/status`
    )
    return response.data
  }

  async getOptunaTrials(experimentId: number): Promise<OptunaTrial[]> {
    const response = await this.client.get<OptunaTrial[]>(
      `${API_ENDPOINTS.experiments}/${experimentId}/optuna/trials`
    )
    return Array.isArray(response.data) ? response.data : []
  }

  async getOptunaBest(experimentId: number): Promise<{ params: Record<string, unknown>; value: number }> {
    const response = await this.client.get(
      `${API_ENDPOINTS.experiments}/${experimentId}/optuna/best`
    )
    return response.data
  }

  // Models
  async getModels(): Promise<Model[]> {
    const response = await this.client.get<{ models: Model[]; total: number } | Model[]>(API_ENDPOINTS.models)
    // Handle both response formats: { models: [], total: number } or Model[]
    if (Array.isArray(response.data)) {
      return response.data
    }
    if (response.data && typeof response.data === 'object' && 'models' in response.data) {
      return Array.isArray(response.data.models) ? response.data.models : []
    }
    return []
  }

  async getModel(id: number): Promise<Model> {
    const response = await this.client.get<Model>(`${API_ENDPOINTS.models}/${id}`)
    return response.data
  }

  async promoteModel(modelId: number, stage: ModelStage, totpCode: string): Promise<Model> {
    // Use the correct endpoint based on stage
    const endpoint = stage === 'paper' 
      ? `${API_ENDPOINTS.models}/${modelId}/promote/paper`
      : stage === 'production'
      ? `${API_ENDPOINTS.models}/${modelId}/promote/production`
      : `${API_ENDPOINTS.models}/${modelId}/promote/staging`
    
    const response = await this.client.post<Model>(
      endpoint,
      { confirm: true, totp_token: totpCode }
    )
    return response.data
  }

  async rollbackModel(modelId: number, totpCode: string): Promise<Model> {
    const response = await this.client.post<Model>(
      `${API_ENDPOINTS.models}/${modelId}/rollback?confirm=true`,
      { totp_code: totpCode }
    )
    return response.data
  }

  async getPaperSessions(modelId: number): Promise<PaperSession[]> {
    const response = await this.client.get(`${API_ENDPOINTS.models}/${modelId}/paper-sessions`)
    return response.data.sessions || []
  }

  async startPaperSession(modelId: number, startBalance: number = 10000): Promise<PaperSession> {
    const response = await this.client.post(
      `${API_ENDPOINTS.models}/${modelId}/paper-sessions/start`,
      { start_balance: startBalance }
    )
    return response.data
  }

  async stopPaperSession(modelId: number, sessionId: number): Promise<PaperSession> {
    const response = await this.client.post(
      `${API_ENDPOINTS.models}/${modelId}/paper-sessions/${sessionId}/stop`
    )
    return response.data
  }

  async getModelValidation(modelId: number): Promise<ValidationResult> {
    const response = await this.client.get(`${API_ENDPOINTS.models}/${modelId}/validation`)
    return response.data
  }

  // Trading
  async getTradingStatus(): Promise<TradingStatus> {
    const response = await this.client.get<TradingStatus>(`${API_ENDPOINTS.trading}/status`)
    return response.data
  }

  async triggerKillSwitch(totpCode: string): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.trading}/kill-switch/trigger`, {
      totp_code: totpCode,
    })
  }

  async resetKillSwitch(totpCode: string): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.trading}/kill-switch/reset`, {
      totp_code: totpCode,
    })
  }

  async getCircuitBreakerStatus(): Promise<CircuitBreakerStatus> {
    const response = await this.client.get<CircuitBreakerStatus>(
      `${API_ENDPOINTS.trading}/circuit-breaker/status`
    )
    return response.data
  }

  async resetCircuitBreaker(totpCode: string): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.trading}/circuit-breaker/reset`, {
      totp_code: totpCode,
    })
  }

  // MT5 Accounts
  async getMT5Accounts(): Promise<MT5Account[]> {
    const response = await this.client.get<{ accounts: MT5Account[]; total: number } | MT5Account[]>(API_ENDPOINTS.mt5Accounts)
    // Handle both response formats: { accounts: [], total: number } or MT5Account[]
    if (Array.isArray(response.data)) {
      return response.data
    }
    if (response.data && typeof response.data === 'object' && 'accounts' in response.data) {
      return Array.isArray(response.data.accounts) ? response.data.accounts : []
    }
    return []
  }

  async postMt5AccountRegister(payload: MT5AccountCreatePayload): Promise<MT5Account> {
    // Response no longer includes auth_token, server_host, server_port for Python API accounts
    const response = await this.client.post<MT5Account>(
      `${API_ENDPOINTS.mt5Accounts}/register`,
      payload
    )
    return response.data
  }

  async getMT5Account(id: number): Promise<MT5Account> {
    const response = await this.client.get<MT5Account>(`${API_ENDPOINTS.mt5Accounts}/${id}`)
    return response.data
  }

  async assignModel(accountId: number, modelId: number, totpCode: string): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.mt5Accounts}/${accountId}/assign-model`, {
      model_id: modelId,
      totp_code: totpCode,
    })
  }

  async pauseTrading(accountId: number): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.mt5Accounts}/${accountId}/pause`)
  }

  async resumeTrading(accountId: number): Promise<void> {
    await this.client.post(`${API_ENDPOINTS.mt5Accounts}/${accountId}/resume`)
  }

  async getAssignment(accountId: number): Promise<ModelAssignment> {
    const response = await this.client.get<ModelAssignment>(
      `${API_ENDPOINTS.mt5Accounts}/${accountId}/assignment`
    )
    return response.data
  }

  // Performance
  async getPortfolioMetrics(period: string = 'all_time'): Promise<PortfolioMetrics> {
    const response = await this.client.get<PortfolioMetrics>(
      `${API_ENDPOINTS.performance}/portfolio`,
      { params: { period } }
    )
    return response.data
  }

  async getPortfolioEquityCurve(startDate?: string, endDate?: string): Promise<EquityPoint[]> {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const response = await this.client.get<{ data: EquityPoint[] }>(
      `${API_ENDPOINTS.performance}/portfolio/equity-curve`,
      { params }
    )
    return Array.isArray(response.data?.data) ? response.data.data : []
  }

  async getPerformanceBreakdown(period: string = 'day'): Promise<PerformanceBreakdown[]> {
    const response = await this.client.get<PerformanceBreakdown[]>(
      `${API_ENDPOINTS.performance}/portfolio/breakdown`,
      { params: { period } }
    )
    return Array.isArray(response.data) ? response.data : []
  }

  async getAllocation(): Promise<{ by_pair: Record<string, number>; by_model: Record<string, number> }> {
    const response = await this.client.get<{ by_pair: Record<string, number>; by_model: Record<string, number> }>(
      `${API_ENDPOINTS.performance}/portfolio/allocation`
    )
    return response.data
  }

  async listModelPerformance(): Promise<ModelMetrics[]> {
    const response = await this.client.get<ModelMetrics[]>(
      `${API_ENDPOINTS.performance}/models`
    )
    return Array.isArray(response.data) ? response.data : []
  }

  async getModelMetrics(modelId: number, period: string = 'all_time'): Promise<ModelMetrics> {
    const response = await this.client.get<ModelMetrics>(
      `${API_ENDPOINTS.performance}/models/${modelId}`,
      { params: { period } }
    )
    return response.data
  }

  async getModelEquityCurve(modelId: number, startDate?: string, endDate?: string): Promise<EquityPoint[]> {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const response = await this.client.get<{ data: EquityPoint[] }>(
      `${API_ENDPOINTS.performance}/models/${modelId}/equity-curve`,
      { params }
    )
    return Array.isArray(response.data?.data) ? response.data.data : []
  }

  async getModelTrades(modelId: number, limit: number = 100, offset: number = 0): Promise<{ trades: Trade[]; total: number }> {
    const response = await this.client.get<{ trades: Trade[]; total: number }>(
      `${API_ENDPOINTS.performance}/models/${modelId}/trades`,
      { params: { limit, offset } }
    )
    return response.data
  }

  async getModelStatistics(modelId: number, period: string = 'all_time'): Promise<ModelStatistics> {
    const response = await this.client.get<ModelStatistics>(
      `${API_ENDPOINTS.performance}/models/${modelId}/statistics`,
      { params: { period } }
    )
    return response.data
  }

  async getModelComparison(modelId: number): Promise<ModelComparison> {
    const response = await this.client.get<ModelComparison>(
      `${API_ENDPOINTS.performance}/models/${modelId}/comparison`
    )
    return response.data
  }

  async getRealtimeMetrics(): Promise<Record<string, unknown>> {
    const response = await this.client.get<Record<string, unknown>>(
      `${API_ENDPOINTS.performance}/metrics/realtime`
    )
    return response.data
  }

  async getEquityCurve(modelId?: number): Promise<EquityPoint[]> {
    if (modelId) {
      return this.getModelEquityCurve(modelId)
    }
    return this.getPortfolioEquityCurve()
  }

  // Currency Pairs
  async getCurrencyPairs(): Promise<string[]> {
    const response = await this.client.get<{ pairs: string[]; total: number }>(
      `${API_ENDPOINTS.trading}/currency-pairs`
    )
    return Array.isArray(response.data?.pairs) ? response.data.pairs : []
  }

  // Positions
  async getPositions(): Promise<any[]> {
    const response = await this.client.get<any[]>(`${API_ENDPOINTS.trading}/positions`)
    return Array.isArray(response.data) ? response.data : []
  }

  // Trade History
  async getTradeHistory(filters?: {
    symbol?: string;
    startDate?: string;
    endDate?: string;
    experimentId?: number;
    limit?: number;
    offset?: number;
  }): Promise<{ trades: Trade[]; total: number }> {
    const response = await this.client.get<{ trades: Trade[]; total: number }>(
      `${API_ENDPOINTS.trading}/history`,
      { params: filters }
    )
    return response.data
  }

  // Parameter Importance (Optuna)
  async getParameterImportance(experimentId: number): Promise<any> {
    const response = await this.client.get(
      `${API_ENDPOINTS.experiments}/${experimentId}/optuna/importance`
    )
    return response.data
  }
}

// Re-export the singleton instance from api-factory to ensure all components use the same instance
export { api } from './api-factory'
