import { createContext, useContext, useEffect, useState, useCallback, useMemo, ReactNode } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { wsService } from '@/services/websocket'

interface WebSocketContextValue {
  isConnected: boolean
  subscribe: <T>(channel: string, handler: (data: T) => void) => () => void
  send: (channel: string, message: unknown) => void
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(undefined)

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnected] = useState(false)
  const { getToken, isSignedIn } = useAuth()

  useEffect(() => {
    // Set token getter for WebSocket service
    wsService.setTokenGetter(getToken)
  }, [getToken])

  useEffect(() => {
    // Only connect if user is signed in
    if (isSignedIn) {
      wsService.connect().catch((error) => {
        console.error('Error connecting WebSocket:', error)
      })
    } else {
      wsService.disconnect()
    }

    // Monitor connection state
    const checkConnection = () => {
      setIsConnected(wsService.isConnected())
    }

    // Initial check
    checkConnection()

    // Poll connection state (WebSocket service doesn't expose events, so we poll)
    const interval = setInterval(checkConnection, 1000)

    return () => {
      clearInterval(interval)
      if (!isSignedIn) {
        wsService.disconnect()
      }
    }
  }, [isSignedIn])

  const subscribe = useCallback(<T,>(channel: string, handler: (data: T) => void) => {
    return wsService.subscribe(channel, handler as (data: unknown) => void)
  }, [])

  const send = useCallback((channel: string, message: unknown) => {
    wsService.send(channel, message)
  }, [])

  const value = useMemo(
    () => ({
      isConnected,
      subscribe,
      send,
    }),
    [isConnected, subscribe, send]
  )

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider')
  }
  return context
}
