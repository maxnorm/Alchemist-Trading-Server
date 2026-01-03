import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'

export function useExperiments() {
  const { data: experiments, isLoading, error, refetch } = useQuery({
    queryKey: ['experiments'],
    queryFn: () => api.getExperiments(),
  })

  return {
    experiments: experiments || [],
    isLoading,
    error,
    refetch,
  }
}
