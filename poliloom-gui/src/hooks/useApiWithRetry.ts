import { useSession } from "next-auth/react"
import { useCallback } from "react"

interface ApiRetryOptions {
  maxRetries?: number
  retryDelay?: number
}

export function useApiWithRetry({ maxRetries = 1, retryDelay = 1000 }: ApiRetryOptions = {}) {
  const { update } = useSession()

  const fetchWithRetry = useCallback(async (
    url: string, 
    options: RequestInit = {},
    retryCount = 0
  ): Promise<Response> => {
    const response = await fetch(url, options)

    // If we get a 401 and haven't exhausted retries, attempt to refresh session and retry
    if (response.status === 401 && retryCount < maxRetries) {
      // Force session refresh by calling update() which will trigger the JWT callback
      await update()
      
      // Wait a bit for the token refresh to complete
      await new Promise(resolve => setTimeout(resolve, retryDelay))
      
      // Retry the request
      return fetchWithRetry(url, options, retryCount + 1)
    }

    return response
  }, [update, maxRetries, retryDelay])

  return { fetchWithRetry }
}