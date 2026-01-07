import { useEffect, useState } from 'react'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { WS_CHANNELS } from '@/services/websocket'
import type { Position } from '@/types/trading'

export function useTradingPositions() {
  const { subscribe } = useWebSocketContext()
  const [positions, setPositions] = useState<Position[]>([])

  useEffect(() => {
    const unsubscribe = subscribe<{ positions: Position[] }>(WS_CHANNELS.tradingPositions, (data) => {
      if (data && typeof data === 'object' && 'positions' in data && Array.isArray(data.positions)) {
        setPositions(data.positions)
      }
    })

    return unsubscribe
  }, [subscribe])

  return { positions }
}
