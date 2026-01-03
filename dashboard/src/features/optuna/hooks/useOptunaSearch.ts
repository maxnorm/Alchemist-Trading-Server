import { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '@/services/api'
import { useOptunaTrials } from '@/hooks/useOptunaTrials'
import toast from 'react-hot-toast'

export function useOptunaSearch() {
  const [selectedExperimentId, setSelectedExperimentId] = useState<number | null>(null)

  const { data: study, refetch: refetchStudy } = useQuery({
    queryKey: ['optuna-status', selectedExperimentId],
    queryFn: () => api.getOptunaStatus(selectedExperimentId!),
    enabled: !!selectedExperimentId,
    refetchInterval: 5000,
  })

  const { data: trialsData, refetch: refetchTrials } = useQuery({
    queryKey: ['optuna-trials', selectedExperimentId],
    queryFn: () => api.getOptunaTrials(selectedExperimentId!),
    enabled: !!selectedExperimentId,
    refetchInterval: 3000,
  })

  // Get study ID from study data for WebSocket subscription
  const studyId = study?.id || null
  const { trials: wsTrials } = useOptunaTrials(studyId)

  // Merge WebSocket trials with query trials
  const allTrials = useMemo(() => {
    const queryTrials = trialsData || []
    const merged = [...queryTrials, ...wsTrials]
    // Remove duplicates by ID
    return Array.from(new Map(merged.map((trial) => [trial.id, trial])).values())
  }, [trialsData, wsTrials])

  const sortedTrials = useMemo(() => {
    return [...allTrials].sort((a, b) => {
      if (!a.value || !b.value) return 0
      return b.value - a.value
    })
  }, [allTrials])

  const startSearchMutation = useMutation({
    mutationFn: (experimentId: number) =>
      api.startOptunaSearch(experimentId, {
        metric: 'sharpe_ratio',
        direction: 'maximize',
        n_trials: 50,
        search_space: {
          learning_rate: { type: 'float', low: 0.00001, high: 0.01, log: true },
          gamma: { type: 'float', low: 0.9, high: 0.999 },
          batch_size: { type: 'categorical', choices: [32, 64, 128] },
        },
        enable_pruning: true,
      }),
    onSuccess: () => {
      toast.success('Optuna search started')
      refetchStudy()
      refetchTrials()
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to start search')
    },
  })

  return {
    selectedExperimentId,
    setSelectedExperimentId,
    study,
    trials: sortedTrials,
    startSearch: startSearchMutation.mutate,
    isStarting: startSearchMutation.isPending,
  }
}
