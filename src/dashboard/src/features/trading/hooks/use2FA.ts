import { useCallback } from 'react'
import { twoFactorService } from '@/services/2fa'

export function use2FA() {
  const verifyCode = useCallback((code: string): boolean => {
    return twoFactorService.verifyCurrentCode(code)
  }, [])

  return {
    verifyCode,
  }
}
