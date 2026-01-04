import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'

export function usePerformanceBreakdown(period: string = 'day') {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['portfolio-breakdown', period],
    queryFn: () => api.getPerformanceBreakdown(period),
  })

  return {
    breakdown: data || [],
    isLoading,
    error,
    refetch,
  }
}
