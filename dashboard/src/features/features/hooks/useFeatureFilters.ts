import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { useDebounce } from '@/hooks/useDebounce'
import type { FeatureFilters } from '@/types/feature'

export function useFeatureFilters() {
  const [filters, setFilters] = useState<FeatureFilters>({})
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedSearchQuery = useDebounce(searchQuery, 300)

  const { data: features, isLoading } = useQuery({
    queryKey: ['features', filters],
    queryFn: () => api.getFeatures(filters),
  })

  const filteredFeatures = useMemo(() => {
    if (!features) return []
    if (!debouncedSearchQuery) return features

    const query = debouncedSearchQuery.toLowerCase()
    return features.filter(
      (feature) =>
        feature.name.toLowerCase().includes(query) ||
        feature.description?.toLowerCase().includes(query)
    )
  }, [features, debouncedSearchQuery])

  return {
    features: filteredFeatures,
    isLoading,
    filters,
    setFilters,
    searchQuery,
    setSearchQuery,
  }
}
