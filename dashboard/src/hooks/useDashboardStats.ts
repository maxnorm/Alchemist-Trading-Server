import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { useTradingStore } from '@/stores/tradingStore'
import type { ModelMetrics } from '@/types/performance'
import type { Experiment } from '@/types/experiment'
import type { Model } from '@/types/model'

interface ActivityItem {
  id: string
  type: 'trade' | 'experiment' | 'model' | 'alert'
  message: string
  timestamp: string
  link?: string
}

interface QuickStats {
  experiments: {
    total: number
    active: number
    completed: number
  }
  models: {
    staging: number
    paper: number
    production: number
  }
  features: number
  accounts: {
    total: number
    active: number
  }
}

export function useDashboardStats() {
  const { data: modelPerformance } = useQuery({
    queryKey: ['model-performance-list'],
    queryFn: () => api.listModelPerformance(),
  })

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  const { data: experiments } = useQuery({
    queryKey: ['experiments'],
    queryFn: () => api.getExperiments(),
  })

  const { status } = useTradingStore()

  const { data: circuitBreaker } = useQuery({
    queryKey: ['circuit-breaker'],
    queryFn: () => api.getCircuitBreakerStatus(),
  })

  const { data: features } = useQuery({
    queryKey: ['features'],
    queryFn: () => api.getFeatures(),
  })

  const { data: mt5Accounts } = useQuery({
    queryKey: ['mt5-accounts'],
    queryFn: () => api.getMT5Accounts(),
  })

  const topModels = useMemo(() => {
    if (!modelPerformance || !models) return []

    return modelPerformance
      .map((perf: ModelMetrics & { model_id: number }) => {
        const model = models.find((m: Model) => m.id === perf.model_id)
        return { ...perf, model }
      })
      .filter((item: any) => item.model)
      .sort((a: any, b: any) => (b.total_pnl || 0) - (a.total_pnl || 0))
      .slice(0, 5)
  }, [modelPerformance, models])

  const recentActivity = useMemo<ActivityItem[]>(() => {
    const activities: ActivityItem[] = []

    // Add recent experiments
    if (experiments) {
      experiments
        .filter((exp: Experiment) => exp.status === 'training')
        .slice(0, 3)
        .forEach((exp: Experiment) => {
          activities.push({
            id: `exp-${exp.id}`,
            type: 'experiment',
            message: `Experiment "${exp.name}" is ${exp.status}`,
            timestamp: exp.started_at || exp.created_at,
            link: `/experiments`,
          })
        })
    }

    // Add model promotions
    if (models) {
      models
        .filter(
          (m: Model) =>
            m.promoted_at &&
            new Date(m.promoted_at) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
        )
        .slice(0, 2)
        .forEach((model: Model) => {
          activities.push({
            id: `model-${model.id}`,
            type: 'model',
            message: `Model v${model.version} promoted to ${model.stage}`,
            timestamp: model.promoted_at!,
            link: `/models`,
          })
        })
    }

    // Add alerts
    if (status?.kill_switch_active) {
      activities.push({
        id: 'alert-killswitch',
        type: 'alert',
        message: 'Kill switch is active',
        timestamp: new Date().toISOString(),
        link: '/trading',
      })
    }

    if (circuitBreaker?.is_active) {
      activities.push({
        id: 'alert-circuitbreaker',
        type: 'alert',
        message: `Circuit breaker triggered: ${circuitBreaker.breaker_type}`,
        timestamp: circuitBreaker.triggered_at || new Date().toISOString(),
        link: '/trading',
      })
    }

    return activities
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 10)
  }, [experiments, models, status, circuitBreaker])

  const quickStats = useMemo<QuickStats>(() => {
    const activeExperiments = experiments?.filter((e: Experiment) => e.status === 'training').length || 0
    const totalExperiments = experiments?.length || 0
    const completedExperiments = experiments?.filter((e: Experiment) => e.status === 'completed').length || 0

    const modelsByStage = {
      staging: models?.filter((m: Model) => m.stage === 'staging').length || 0,
      paper: models?.filter((m: Model) => m.stage === 'paper').length || 0,
      production: models?.filter((m: Model) => m.stage === 'production').length || 0,
    }

    const activeAccounts = mt5Accounts?.filter((acc: any) => acc.is_active).length || 0
    const totalAccounts = mt5Accounts?.length || 0

    return {
      experiments: { total: totalExperiments, active: activeExperiments, completed: completedExperiments },
      models: modelsByStage,
      features: features?.length || 0,
      accounts: { total: totalAccounts, active: activeAccounts },
    }
  }, [experiments, models, features, mt5Accounts])

  return {
    topModels,
    recentActivity,
    quickStats,
  }
}
