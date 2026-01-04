import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import type { EquityPoint } from '@/types/performance'

export function useEquityCurve(modelId?: number, startDate?: string, endDate?: string) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: modelId
      ? ['model-equity-curve', modelId, startDate, endDate]
      : ['portfolio-equity-curve', startDate, endDate],
    queryFn: () =>
      modelId
        ? api.getModelEquityCurve(modelId, startDate, endDate)
        : api.getPortfolioEquityCurve(startDate, endDate),
    enabled: modelId !== undefined || modelId === undefined,
  })

  return {
    equityCurve: (data || []) as EquityPoint[],
    isLoading,
    error,
    refetch,
  }
}
