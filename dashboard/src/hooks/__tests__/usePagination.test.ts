import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePagination } from '../usePagination'

describe('usePagination', () => {
  const mockData = Array.from({ length: 50 }, (_, i) => ({ id: i, name: `Item ${i}` }))

  it('should initialize with first page', () => {
    const { result } = renderHook(() => usePagination(mockData, { pageSize: 10 }))

    expect(result.current.page).toBe(1)
    expect(result.current.pageSize).toBe(10)
    expect(result.current.totalPages).toBe(5)
    expect(result.current.paginatedData).toHaveLength(10)
    expect(result.current.hasNextPage).toBe(true)
    expect(result.current.hasPreviousPage).toBe(false)
  })

  it('should paginate data correctly', () => {
    const { result } = renderHook(() => usePagination(mockData, { pageSize: 10 }))

    expect(result.current.paginatedData[0].id).toBe(0)
    expect(result.current.paginatedData[9].id).toBe(9)

    act(() => {
      result.current.setPage(2)
    })

    expect(result.current.page).toBe(2)
    expect(result.current.paginatedData[0].id).toBe(10)
    expect(result.current.paginatedData[9].id).toBe(19)
  })

  it('should navigate pages correctly', () => {
    const { result } = renderHook(() => usePagination(mockData, { pageSize: 10 }))

    act(() => {
      result.current.goToNextPage()
    })
    expect(result.current.page).toBe(2)

    act(() => {
      result.current.goToPreviousPage()
    })
    expect(result.current.page).toBe(1)

    act(() => {
      result.current.goToLastPage()
    })
    expect(result.current.page).toBe(5)
    expect(result.current.hasNextPage).toBe(false)

    act(() => {
      result.current.goToFirstPage()
    })
    expect(result.current.page).toBe(1)
  })

  it('should handle empty data', () => {
    const { result } = renderHook(() => usePagination([], { pageSize: 10 }))

    expect(result.current.totalPages).toBe(1)
    expect(result.current.paginatedData).toHaveLength(0)
    expect(result.current.hasNextPage).toBe(false)
    expect(result.current.hasPreviousPage).toBe(false)
  })
})
