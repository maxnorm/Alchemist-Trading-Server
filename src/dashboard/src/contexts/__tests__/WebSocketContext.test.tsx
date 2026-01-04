import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WebSocketProvider, useWebSocketContext } from '../WebSocketContext'
import { wsService } from '@/services/websocket'

// Mock the WebSocket service
vi.mock('@/services/websocket', () => ({
  wsService: {
    connect: vi.fn(),
    isConnected: vi.fn(() => true),
    subscribe: vi.fn(() => () => {}),
    send: vi.fn(),
  },
}))

function TestComponent() {
  const { isConnected, subscribe, send } = useWebSocketContext()
  return (
    <div>
      <div data-testid="connected">{isConnected ? 'connected' : 'disconnected'}</div>
      <button
        onClick={() => {
          const unsubscribe = subscribe('test', () => {})
          unsubscribe()
        }}
      >
        Subscribe
      </button>
      <button onClick={() => send('test', { data: 'test' })}>Send</button>
    </div>
  )
}

describe('WebSocketContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should provide WebSocket context', () => {
    render(
      <WebSocketProvider>
        <TestComponent />
      </WebSocketProvider>
    )

    expect(screen.getByTestId('connected')).toHaveTextContent('connected')
    expect(wsService.connect).toHaveBeenCalled()
  })

  it('should provide subscribe function', () => {
    render(
      <WebSocketProvider>
        <TestComponent />
      </WebSocketProvider>
    )

    const subscribeButton = screen.getByText('Subscribe')
    subscribeButton.click()

    expect(wsService.subscribe).toHaveBeenCalled()
  })

  it('should provide send function', () => {
    render(
      <WebSocketProvider>
        <TestComponent />
      </WebSocketProvider>
    )

    const sendButton = screen.getByText('Send')
    sendButton.click()

    expect(wsService.send).toHaveBeenCalledWith('test', { data: 'test' })
  })
})
