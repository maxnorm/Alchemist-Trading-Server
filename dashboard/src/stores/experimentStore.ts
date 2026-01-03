import { create } from 'zustand'
import type { Experiment } from '@/types/experiment'

interface ExperimentStore {
  experiments: Experiment[]
  selectedExperiment: Experiment | null
  setExperiments: (experiments: Experiment[]) => void
  addExperiment: (experiment: Experiment) => void
  updateExperiment: (id: number, updates: Partial<Experiment>) => void
  setSelectedExperiment: (experiment: Experiment | null) => void
  removeExperiment: (id: number) => void
}

export const useExperimentStore = create<ExperimentStore>((set) => ({
  experiments: [],
  selectedExperiment: null,
  setExperiments: (experiments) => set({ experiments }),
  addExperiment: (experiment) =>
    set((state) => ({
      experiments: [...state.experiments, experiment],
    })),
  updateExperiment: (id, updates) =>
    set((state) => ({
      experiments: state.experiments.map((exp) =>
        exp.id === id ? { ...exp, ...updates } : exp
      ),
      selectedExperiment:
        state.selectedExperiment?.id === id
          ? { ...state.selectedExperiment, ...updates }
          : state.selectedExperiment,
    })),
  setSelectedExperiment: (experiment) => set({ selectedExperiment: experiment }),
  removeExperiment: (id) =>
    set((state) => ({
      experiments: state.experiments.filter((exp) => exp.id !== id),
      selectedExperiment:
        state.selectedExperiment?.id === id ? null : state.selectedExperiment,
    })),
}))
