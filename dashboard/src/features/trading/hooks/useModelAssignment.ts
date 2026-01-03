import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { twoFactorService } from '@/services/2fa'
import { useModalController } from '@/hooks/useModalController'
import toast from 'react-hot-toast'

export function useModelAssignment() {
  const queryClient = useQueryClient()
  const { isOpen: showDialog, open: openDialog, close: closeDialog } = useModalController()
  const [assignAccountId, setAssignAccountId] = useState<number | null>(null)
  const [assignModelId, setAssignModelId] = useState<number | null>(null)
  const [totpCode, setTotpCode] = useState('')

  const { mutate: assign, isPending } = useMutation({
    mutationFn: ({ accountId, modelId, code }: { accountId: number; modelId: number; code: string }) =>
      api.assignModel(accountId, modelId, code),
    onSuccess: () => {
      toast.success('Model assigned successfully')
      queryClient.invalidateQueries({ queryKey: ['mt5-accounts'] })
      closeDialog()
      setAssignAccountId(null)
      setAssignModelId(null)
      setTotpCode('')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to assign model')
    },
  })

  const handleAssign = useCallback(() => {
    if (!assignAccountId || !assignModelId || !totpCode) {
      toast.error('Please fill all fields')
      return
    }
    if (!twoFactorService.verifyCurrentCode(totpCode)) {
      toast.error('Invalid 2FA code')
      return
    }
    assign({ accountId: assignAccountId, modelId: assignModelId, code: totpCode })
  }, [assignAccountId, assignModelId, totpCode, assign])

  const openAssignmentDialog = useCallback(
    (accountId: number) => {
      setAssignAccountId(accountId)
      openDialog()
    },
    [openDialog]
  )

  return {
    assignAccountId,
    setAssignAccountId,
    assignModelId,
    setAssignModelId,
    totpCode,
    setTotpCode,
    showDialog,
    openAssignmentDialog,
    closeDialog,
    handleAssign,
    isPending,
  }
}
