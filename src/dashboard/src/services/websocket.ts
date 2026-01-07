import { WS_BASE_URL } from '@/utils/constants'

export const WS_CHANNELS = {
  experimentProgress: (id: number) => `/ws/experiments/${id}/progress`,
  trainingMetrics: '/ws/training/metrics',
  optunaTrials: (studyId: number) => `/ws/optuna/${studyId}/trials`,
  tradingStatus: '/ws/trading/status',
  tradingPositions: '/ws/trading/positions',
  performanceUpdates: '/ws/performance/updates',
  alerts: '/ws/alerts',
} as const

type MessageHandler = (data: unknown) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private subscribers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000
  private isConnecting = false
  private shouldReconnect = true

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return
    }

    this.isConnecting = true
    try {
      this.ws = new WebSocket(WS_BASE_URL)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.reconnectDelay = 1000
        
        // Subscribe to all active channels
        this.resubscribeAll()
      }

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.isConnecting = false
      }

      this.ws.onclose = () => {
        console.log('WebSocket disconnected')
        this.isConnecting = false
        if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect()
        }
      }
    } catch (error) {
      console.error('Error creating WebSocket connection:', error)
      this.isConnecting = false
      if (this.shouldReconnect) {
        this.scheduleReconnect()
      }
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000)
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect()
      }
    }, delay)
  }

  private handleMessage(message: { channel?: string; data?: unknown }): void {
    const { channel, data } = message
    if (channel && this.subscribers.has(channel)) {
      const handlers = this.subscribers.get(channel)!
      handlers.forEach((handler) => {
        try {
          // Ensure data is always defined (default to empty object if undefined)
          handler(data ?? {})
        } catch (error) {
          console.error('Error in WebSocket message handler:', error)
        }
      })
    }
  }

  subscribe(channel: string, handler: MessageHandler): () => void {
    if (!this.subscribers.has(channel)) {
      this.subscribers.set(channel, new Set())
    }
    this.subscribers.get(channel)!.add(handler)

    // Ensure connection is open
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect()
    } else {
      // If already connected, send subscription message immediately
      this.sendSubscription(channel)
    }

    // Return unsubscribe function
    return () => {
      const handlers = this.subscribers.get(channel)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.subscribers.delete(channel)
          // Send unsubscribe message if no more handlers for this channel
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.sendUnsubscription(channel)
          }
        }
      }
    }
  }
  
  private sendSubscription(channel: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        channel: channel
      }))
    }
  }
  
  private sendUnsubscription(channel: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'unsubscribe',
        channel: channel
      }))
    }
  }
  
  private resubscribeAll(): void {
    // Resubscribe to all active channels after reconnection
    for (const channel of this.subscribers.keys()) {
      this.sendSubscription(channel)
    }
  }

  unsubscribe(channel: string): void {
    this.subscribers.delete(channel)
  }

  send(channel: string, message: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ channel, data: message }))
    } else {
      console.warn('WebSocket is not connected. Message not sent.')
    }
  }

  disconnect(): void {
    this.shouldReconnect = false
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.subscribers.clear()
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsService = new WebSocketService()
