import { useState, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import toast from 'react-hot-toast'

export function usePaperSession(modelId: number | null) {
  const queryClient = useQueryClient()
  const [paperSessionBalance, setPaperSessionBalance] = useState(10000)

  const { data: paperSessions } = useQuery({
    queryKey: ['paperSessions', modelId],
    queryFn: () => api.getPaperSessions(modelId!),
    enabled: !!modelId,
  })

  const startSessionMutation = useMutation({
    mutationFn: ({ modelId, balance }: { modelId: number; balance: number }) =>
      api.startPaperSession(modelId, balance),
    onSuccess: () => {
      toast.success('Paper trading session started')
      queryClient.invalidateQueries({ queryKey: ['paperSessions'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to start paper session')
    },
  })

  const stopSessionMutation = useMutation({
    mutationFn: ({ modelId, sessionId }: { modelId: number; sessionId: number }) =>
      api.stopPaperSession(modelId, sessionId),
    onSuccess: () => {
      toast.success('Paper trading session stopped')
      queryClient.invalidateQueries({ queryKey: ['paperSessions'] })
      queryClient.invalidateQueries({ queryKey: ['models'] })
      queryClient.invalidateQueries({ queryKey: ['validation'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to stop paper session')
    },
  })

  const handleStartSession = useCallback(
    (modelId: number) => {
      startSessionMutation.mutate({ modelId, balance: paperSessionBalance })
    },
    [paperSessionBalance, startSessionMutation]
  )

  const handleStopSession = useCallback(
    (modelId: number, sessionId: number) => {
      stopSessionMutation.mutate({ modelId, sessionId })
    },
    [stopSessionMutation]
  )

  const runningSession = paperSessions?.find((s: any) => s.status === 'running')

  return {
    paperSessions: paperSessions || [],
    runningSession,
    paperSessionBalance,
    setPaperSessionBalance,
    handleStartSession,
    handleStopSession,
    isStarting: startSessionMutation.isPending,
    isStopping: stopSessionMutation.isPending,
  }
}
