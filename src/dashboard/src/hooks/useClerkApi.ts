import { useEffect } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { api } from '@/services/api-factory'

export function useClerkApi() {
  const { getToken, isLoaded } = useAuth()

  useEffect(() => {
    if (isLoaded && getToken) {
      // Set token getter for API client
      api.setTokenGetter(getToken)
    }
  }, [getToken, isLoaded])

  return api
}
