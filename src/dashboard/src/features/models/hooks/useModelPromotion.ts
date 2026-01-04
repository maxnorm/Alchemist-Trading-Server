import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { twoFactorService } from '@/services/2fa'
import toast from 'react-hot-toast'
import type { ModelStage } from '@/types/model'

export function useModelPromotion() {
  const queryClient = useQueryClient()
  const [promoteModelId, setPromoteModelId] = useState<number | null>(null)
  const [promoteStage, setPromoteStage] = useState<ModelStage | null>(null)
  const [totpCode, setTotpCode] = useState('')

  const { mutate: promote, isPending } = useMutation({
    mutationFn: ({ modelId, stage, code }: { modelId: number; stage: ModelStage; code: string }) =>
      api.promoteModel(modelId, stage, code),
    onSuccess: () => {
      toast.success('Model promoted successfully')
      queryClient.invalidateQueries({ queryKey: ['models'] })
      setPromoteModelId(null)
      setPromoteStage(null)
      setTotpCode('')
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to promote model')
    },
  })

  const handlePromote = useCallback(() => {
    if (!promoteModelId || !promoteStage) {
      toast.error('Missing promotion details')
      return
    }

    // Only require 2FA for production
    if (promoteStage === 'production' && !totpCode) {
      toast.error('Please enter 2FA code for production promotion')
      return
    }

    if (promoteStage === 'production' && !twoFactorService.verifyCurrentCode(totpCode)) {
      toast.error('Invalid 2FA code')
      return
    }

    promote({
      modelId: promoteModelId,
      stage: promoteStage,
      code: totpCode || '000000', // Dummy code for non-production
    })
  }, [promoteModelId, promoteStage, totpCode, promote])

  return {
    promoteModelId,
    setPromoteModelId,
    promoteStage,
    setPromoteStage,
    totpCode,
    setTotpCode,
    handlePromote,
    isPending,
  }
}
