import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { twoFactorService } from '@/services/2fa'
import { useModalController } from '@/hooks/useModalController'
import toast from 'react-hot-toast'

export function useKillSwitch() {
  const queryClient = useQueryClient()
  const { isOpen: showDialog, open: openDialog, close: closeDialog } = useModalController()
  const [killSwitchCode, setKillSwitchCode] = useState('')

  const { mutate: trigger, isPending: isTriggering } = useMutation({
    mutationFn: (code: string) => api.triggerKillSwitch(code),
    onSuccess: () => {
      toast.success('Kill switch activated')
      queryClient.invalidateQueries({ queryKey: ['trading-status'] })
      closeDialog()
      setKillSwitchCode('')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to activate kill switch')
    },
  })

  const { mutate: reset, isPending: isResetting } = useMutation({
    mutationFn: (code: string) => api.resetKillSwitch(code),
    onSuccess: () => {
      toast.success('Kill switch reset')
      queryClient.invalidateQueries({ queryKey: ['trading-status'] })
      closeDialog()
      setKillSwitchCode('')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reset kill switch')
    },
  })

  const handleTrigger = useCallback(() => {
    if (!killSwitchCode) {
      toast.error('Please enter 2FA code')
      return
    }
    if (!twoFactorService.verifyCurrentCode(killSwitchCode)) {
      toast.error('Invalid 2FA code')
      return
    }
    trigger(killSwitchCode)
  }, [killSwitchCode, trigger])

  const handleReset = useCallback(() => {
    if (!killSwitchCode) {
      toast.error('Please enter 2FA code')
      return
    }
    if (!twoFactorService.verifyCurrentCode(killSwitchCode)) {
      toast.error('Invalid 2FA code')
      return
    }
    reset(killSwitchCode)
  }, [killSwitchCode, reset])

  return {
    killSwitchCode,
    setKillSwitchCode,
    showDialog,
    openDialog,
    closeDialog,
    handleTrigger,
    handleReset,
    isTriggering,
    isResetting,
  }
}
