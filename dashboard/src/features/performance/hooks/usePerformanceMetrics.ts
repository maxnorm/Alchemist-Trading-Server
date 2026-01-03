import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import type { PortfolioMetrics, ModelMetrics } from '@/types/performance'

/**
 * Hook for fetching and managing performance metrics with real-time updates
 * @param period - Time period filter (default: 'all_time')
 * @param modelId - Optional model ID for model-specific metrics
 * @returns Performance metrics, loading state, and refetch function
 */
export function usePerformanceMetrics(period: string = 'all_time', modelId?: number) {
  const { subscribe } = useWebSocketContext()

  const queryKey = modelId ? ['model-metrics', modelId, period] : ['portfolio-metrics', period]

  const { data, isLoading, refetch } = useQuery<PortfolioMetrics | ModelMetrics>({
    queryKey,
    queryFn: () =>
      modelId ? api.getModelMetrics(modelId, period) : api.getPortfolioMetrics(period),
    refetchInterval: 30000,
  })

  // WebSocket subscription for real-time updates
  useEffect(() => {
    const unsubscribe = subscribe<{ type: string; data?: { model_id?: number } }>(
      'performanceUpdates',
      (msg) => {
        if (
          msg.type === 'portfolio_update' ||
          (modelId && msg.data?.model_id === modelId)
        ) {
          refetch()
        }
      }
    )
    return unsubscribe
  }, [subscribe, refetch, modelId])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetch()
    }, 30000)
    return () => clearInterval(interval)
  }, [refetch])

  return {
    metrics: data as (PortfolioMetrics | ModelMetrics) | undefined,
    isLoading,
    refetch,
  }
}
