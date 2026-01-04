import { create } from 'zustand'
import type { TradingStatus, Position, CircuitBreakerStatus } from '@/types/trading'

interface TradingStore {
  status: TradingStatus | null
  positions: Position[]
  circuitBreaker: CircuitBreakerStatus | null
  setStatus: (status: TradingStatus) => void
  setPositions: (positions: Position[]) => void
  addPosition: (position: Position) => void
  updatePosition: (id: number, updates: Partial<Position>) => void
  removePosition: (id: number) => void
  setCircuitBreaker: (status: CircuitBreakerStatus) => void
}

export const useTradingStore = create<TradingStore>((set) => ({
  status: null,
  positions: [],
  circuitBreaker: null,
  setStatus: (status) => set({ status }),
  setPositions: (positions) => set({ positions }),
  addPosition: (position) =>
    set((state) => ({
      positions: [...state.positions, position],
    })),
  updatePosition: (id, updates) =>
    set((state) => ({
      positions: state.positions.map((p) => (p.id === id ? { ...p, ...updates } : p)),
    })),
  removePosition: (id) =>
    set((state) => ({
      positions: state.positions.filter((p) => p.id !== id),
    })),
  setCircuitBreaker: (circuitBreaker) => set({ circuitBreaker }),
}))
