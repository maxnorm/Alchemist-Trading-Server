import { useState, useCallback } from 'react'

interface UseModalControllerReturn {
  isOpen: boolean
  open: () => void
  close: () => void
  toggle: () => void
}

/**
 * Hook for managing modal open/close state
 * @param initialState - Initial open state (default: false)
 * @returns Modal state and control functions
 */
export function useModalController(initialState: boolean = false): UseModalControllerReturn {
  const [isOpen, setIsOpen] = useState(initialState)

  const open = useCallback(() => {
    setIsOpen(true)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
  }, [])

  const toggle = useCallback(() => {
    setIsOpen((prev) => !prev)
  }, [])

  return {
    isOpen,
    open,
    close,
    toggle,
  }
}
