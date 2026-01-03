import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { useTradingStore } from '@/stores/tradingStore'

export function useTradingStatus() {
  const { status, setStatus } = useTradingStore()

  const { data: tradingStatus, isLoading, refetch } = useQuery({
    queryKey: ['trading-status'],
    queryFn: () => api.getTradingStatus(),
    refetchInterval: 5000,
  })

  useEffect(() => {
    if (tradingStatus) {
      setStatus(tradingStatus)
    }
  }, [tradingStatus, setStatus])

  return {
    status: status || tradingStatus,
    isLoading,
    refetch,
  }
}
