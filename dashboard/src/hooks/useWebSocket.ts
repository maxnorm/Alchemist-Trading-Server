import { useEffect, useState } from 'react'
import { useWebSocketContext } from '@/contexts/WebSocketContext'

/**
 * Generic WebSocket hook for subscribing to a channel
 * @param channel - The WebSocket channel to subscribe to
 * @returns The last message received on the channel
 */
export function useWebSocket<T = any>(channel: string) {
  const { subscribe } = useWebSocketContext()
  const [lastMessage, setLastMessage] = useState<T | null>(null)

  useEffect(() => {
    const unsubscribe = subscribe<T>(channel, (data) => {
      setLastMessage(data)
    })

    return unsubscribe
  }, [channel, subscribe])

  return { lastMessage }
}
