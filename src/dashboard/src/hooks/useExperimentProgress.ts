import { useEffect, useState, useMemo } from 'react'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { WS_CHANNELS } from '@/services/websocket'
import type { ExperimentProgress } from '@/types/experiment'

export function useExperimentProgress(experimentId: number | null) {
  const { subscribe } = useWebSocketContext()
  const [progressData, setProgressData] = useState<ExperimentProgress[]>([])

  useEffect(() => {
    if (!experimentId) return

    const unsubscribe = subscribe<ExperimentProgress>(
      WS_CHANNELS.experimentProgress(experimentId),
      (data) => {
        setProgressData((prev) => [...prev, data].slice(-50)) // Keep last 50 updates
      }
    )

    return unsubscribe
  }, [experimentId, subscribe])

  const latest = useMemo(() => {
    return progressData.length > 0 ? progressData[progressData.length - 1] : null
  }, [progressData])

  return {
    progress: progressData,
    latest,
  }
}
