import { TOTP } from 'otpauth'
import QRCode from 'qrcode'

const STORAGE_KEY = 'alchemist_2fa_secret'
const STORAGE_ENABLED_KEY = 'alchemist_2fa_enabled'

class TwoFactorService {
  private secret: string | null = null

  constructor() {
    // Load secret from localStorage
    this.secret = localStorage.getItem(STORAGE_KEY)
  }

  generateSecret(): string {
    const secret = new TOTP({
      issuer: 'The Alchemist',
      label: 'Alchemist Dashboard',
      algorithm: 'SHA1',
      digits: 6,
      period: 30,
    }).secret.base32

    this.secret = secret
    localStorage.setItem(STORAGE_KEY, secret)
    return secret
  }

  async getQRCode(secret: string, label: string = 'Alchemist Dashboard'): Promise<string> {
    const totp = new TOTP({
      secret,
      issuer: 'The Alchemist',
      label,
      algorithm: 'SHA1',
      digits: 6,
      period: 30,
    })

    const uri = totp.toString()
    return QRCode.toDataURL(uri)
  }

  verifyCode(secret: string, code: string): boolean {
    try {
      const totp = new TOTP({
        secret,
        algorithm: 'SHA1',
        digits: 6,
        period: 30,
      })

      const token = totp.generate()
      return token === code
    } catch (error) {
      console.error('Error verifying TOTP code:', error)
      return false
    }
  }

  verifyCurrentCode(code: string): boolean {
    if (!this.secret) {
      return false
    }
    return this.verifyCode(this.secret, code)
  }

  isEnabled(): boolean {
    return localStorage.getItem(STORAGE_ENABLED_KEY) === 'true' && this.secret !== null
  }

  enable(secret?: string): void {
    if (secret) {
      this.secret = secret
      localStorage.setItem(STORAGE_KEY, secret)
    } else if (!this.secret) {
      this.generateSecret()
    }
    localStorage.setItem(STORAGE_ENABLED_KEY, 'true')
  }

  disable(): void {
    localStorage.removeItem(STORAGE_ENABLED_KEY)
    // Keep secret in case user wants to re-enable
  }

  getSecret(): string | null {
    return this.secret
  }

  reset(): void {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(STORAGE_ENABLED_KEY)
    this.secret = null
  }
}

export const twoFactorService = new TwoFactorService()
