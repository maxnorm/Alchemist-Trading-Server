import { useReducer, useCallback, useMemo } from 'react'
import type { CreateExperimentDto } from '@/types/experiment'

type ExperimentFormAction =
  | { type: 'SET_FIELD'; field: keyof CreateExperimentDto; value: any }
  | { type: 'TOGGLE_FEATURE'; name: string }
  | { type: 'TOGGLE_CURRENCY_PAIR'; pair: string }
  | { type: 'RESET' }
  | { type: 'SELECT_ALL_PAIRS'; pairs: string[] }
  | { type: 'DESELECT_ALL_PAIRS' }

const initialFormState: CreateExperimentDto = {
  name: '',
  description: '',
  features: [],
  currency_pairs: [],
  training_mode: 'live',
  hyperparameters: {},
}

function experimentFormReducer(
  state: CreateExperimentDto,
  action: ExperimentFormAction
): CreateExperimentDto {
  switch (action.type) {
    case 'SET_FIELD':
      return {
        ...state,
        [action.field]: action.value,
      }
    case 'TOGGLE_FEATURE':
      return {
        ...state,
        features: state.features.includes(action.name)
          ? state.features.filter((f) => f !== action.name)
          : [...state.features, action.name],
      }
    case 'TOGGLE_CURRENCY_PAIR':
      return {
        ...state,
        currency_pairs: state.currency_pairs.includes(action.pair)
          ? state.currency_pairs.filter((p) => p !== action.pair)
          : [...state.currency_pairs, action.pair],
      }
    case 'SELECT_ALL_PAIRS':
      return {
        ...state,
        currency_pairs: [...action.pairs],
      }
    case 'DESELECT_ALL_PAIRS':
      return {
        ...state,
        currency_pairs: [],
      }
    case 'RESET':
      return initialFormState
    default:
      return state
  }
}

/**
 * Hook for managing experiment form state with validation
 * @returns Form state, actions, errors, and validation status
 */
export function useExperimentForm() {
  const [formData, dispatch] = useReducer(experimentFormReducer, initialFormState)

  const toggleFeature = useCallback((name: string) => {
    dispatch({ type: 'TOGGLE_FEATURE', name })
  }, [])

  const toggleCurrencyPair = useCallback((pair: string) => {
    dispatch({ type: 'TOGGLE_CURRENCY_PAIR', pair })
  }, [])

  const selectAllCurrencyPairs = useCallback((pairs: string[]) => {
    dispatch({ type: 'SELECT_ALL_PAIRS', pairs })
  }, [])

  const deselectAllCurrencyPairs = useCallback(() => {
    dispatch({ type: 'DESELECT_ALL_PAIRS' })
  }, [])

  const setField = useCallback((field: keyof CreateExperimentDto, value: any) => {
    dispatch({ type: 'SET_FIELD', field, value })
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' })
  }, [])

  const validate = useCallback(() => {
    const errors: Record<string, string> = {}
    if (!formData.name.trim()) {
      errors.name = 'Experiment name is required'
    }
    if (formData.features.length === 0) {
      errors.features = 'At least one feature must be selected'
    }
    if (formData.currency_pairs.length === 0) {
      errors.currency_pairs = 'At least one currency pair must be selected'
    }
    return errors
  }, [formData])

  const errors = useMemo(() => validate(), [validate])
  const isValid = useMemo(() => Object.keys(errors).length === 0, [errors])

  return {
    formData,
    actions: {
      toggleFeature,
      toggleCurrencyPair,
      selectAllCurrencyPairs,
      deselectAllCurrencyPairs,
      setField,
      reset,
    },
    errors,
    isValid,
  }
}
