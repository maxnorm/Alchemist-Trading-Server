import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import type { Model, ModelStage } from '@/types/model'

export function useModels(stage?: ModelStage | 'all') {
  const { data: modelsData, isLoading, error, refetch } = useQuery({
    queryKey: ['models', stage],
    queryFn: () => api.getModels(),
  })

  const models: Model[] = modelsData || []
  const filteredModels =
    stage === 'all' || !stage ? models : models.filter((m) => m.stage === stage)

  return {
    models,
    filteredModels,
    isLoading,
    error,
    refetch,
  }
}
