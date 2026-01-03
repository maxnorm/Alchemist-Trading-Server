import { useState, useMemo } from 'react'

export type Period = 'today' | 'this_week' | 'this_month' | 'this_year' | 'all_time'

const PERIODS: Period[] = ['today', 'this_week', 'this_month', 'this_year', 'all_time']

interface UsePeriodFilterReturn {
  period: Period
  setPeriod: (period: Period) => void
  periods: Period[]
  formattedPeriod: string
}

/**
 * Hook for managing time period filter state
 * @param defaultPeriod - Initial period value (default: 'all_time')
 * @returns Period state and formatted string
 */
export function usePeriodFilter(defaultPeriod: Period = 'all_time'): UsePeriodFilterReturn {
  const [period, setPeriod] = useState<Period>(defaultPeriod)

  const formattedPeriod = useMemo(() => {
    return period.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  }, [period])

  return {
    period,
    setPeriod,
    periods: PERIODS,
    formattedPeriod,
  }
}
