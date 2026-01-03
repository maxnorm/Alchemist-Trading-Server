import { useEffect, useState } from 'react'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { WS_CHANNELS } from '@/services/websocket'
import type { OptunaTrial } from '@/types/optuna'

export function useOptunaTrials(studyId: number | null) {
  const { subscribe } = useWebSocketContext()
  const [trials, setTrials] = useState<OptunaTrial[]>([])

  useEffect(() => {
    if (!studyId) return

    const unsubscribe = subscribe<{ trial: OptunaTrial }>(WS_CHANNELS.optunaTrials(studyId), (data) => {
      if (data.trial) {
        setTrials((prev) => {
          const existing = prev.findIndex((t) => t.id === data.trial.id)
          if (existing >= 0) {
            return prev.map((t, i) => (i === existing ? data.trial : t))
          }
          return [...prev, data.trial]
        })
      }
    })

    return unsubscribe
  }, [studyId, subscribe])

  return { trials, setTrials }
}
