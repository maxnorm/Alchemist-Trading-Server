import { create } from 'zustand'
import type { Model } from '@/types/model'

interface ModelStore {
  models: Model[]
  selectedModel: Model | null
  setModels: (models: Model[]) => void
  addModel: (model: Model) => void
  updateModel: (id: number, updates: Partial<Model>) => void
  setSelectedModel: (model: Model | null) => void
  removeModel: (id: number) => void
}

export const useModelStore = create<ModelStore>((set) => ({
  models: [],
  selectedModel: null,
  setModels: (models) => set({ models }),
  addModel: (model) =>
    set((state) => ({
      models: [...state.models, model],
    })),
  updateModel: (id, updates) =>
    set((state) => ({
      models: state.models.map((m) => (m.id === id ? { ...m, ...updates } : m)),
      selectedModel:
        state.selectedModel?.id === id
          ? { ...state.selectedModel, ...updates }
          : state.selectedModel,
    })),
  setSelectedModel: (model) => set({ selectedModel: model }),
  removeModel: (id) =>
    set((state) => ({
      models: state.models.filter((m) => m.id !== id),
      selectedModel: state.selectedModel?.id === id ? null : state.selectedModel,
    })),
}))
