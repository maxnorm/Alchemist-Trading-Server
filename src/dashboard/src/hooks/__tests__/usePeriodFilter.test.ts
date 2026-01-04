import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePeriodFilter } from '../usePeriodFilter'

describe('usePeriodFilter', () => {
  it('should initialize with default period', () => {
    const { result } = renderHook(() => usePeriodFilter('all_time'))

    expect(result.current.period).toBe('all_time')
    expect(result.current.periods).toHaveLength(5)
    expect(result.current.formattedPeriod).toBe('All Time')
  })

  it('should change period correctly', () => {
    const { result } = renderHook(() => usePeriodFilter('all_time'))

    act(() => {
      result.current.setPeriod('today')
    })

    expect(result.current.period).toBe('today')
    expect(result.current.formattedPeriod).toBe('Today')
  })

  it('should format period correctly', () => {
    const { result } = renderHook(() => usePeriodFilter('this_week'))

    expect(result.current.formattedPeriod).toBe('This Week')
  })
})
