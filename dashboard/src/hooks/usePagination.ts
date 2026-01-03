import { useState, useMemo } from 'react'

interface UsePaginationOptions {
  pageSize?: number
  initialPage?: number
}

interface UsePaginationReturn<T> {
  page: number
  setPage: (page: number) => void
  pageSize: number
  totalPages: number
  paginatedData: T[]
  hasNextPage: boolean
  hasPreviousPage: boolean
  goToNextPage: () => void
  goToPreviousPage: () => void
  goToFirstPage: () => void
  goToLastPage: () => void
}

/**
 * Hook for managing pagination state and logic
 * @param data - Array of data to paginate
 * @param options - Pagination options (pageSize, initialPage)
 * @returns Pagination state and navigation functions
 */
export function usePagination<T>(
  data: T[],
  options: UsePaginationOptions = {}
): UsePaginationReturn<T> {
  const { pageSize = 20, initialPage = 1 } = options
  const [page, setPage] = useState(initialPage)

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(data.length / pageSize))
  }, [data.length, pageSize])

  const paginatedData = useMemo(() => {
    const startIndex = (page - 1) * pageSize
    const endIndex = startIndex + pageSize
    return data.slice(startIndex, endIndex)
  }, [data, page, pageSize])

  const hasNextPage = page < totalPages
  const hasPreviousPage = page > 1

  const goToNextPage = () => {
    if (hasNextPage) {
      setPage((prev) => prev + 1)
    }
  }

  const goToPreviousPage = () => {
    if (hasPreviousPage) {
      setPage((prev) => prev - 1)
    }
  }

  const goToFirstPage = () => {
    setPage(1)
  }

  const goToLastPage = () => {
    setPage(totalPages)
  }

  return {
    page,
    setPage,
    pageSize,
    totalPages,
    paginatedData,
    hasNextPage,
    hasPreviousPage,
    goToNextPage,
    goToPreviousPage,
    goToFirstPage,
    goToLastPage,
  }
}
