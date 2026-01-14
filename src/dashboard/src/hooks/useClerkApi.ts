import { useEffect } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { api } from '@/services/api'

export function useClerkApi() {
  const { getToken } = useAuth()

  useEffect(() => {
    // Set token getter for API client
    api.setTokenGetter(getToken)
  }, [getToken])

  return api
}
