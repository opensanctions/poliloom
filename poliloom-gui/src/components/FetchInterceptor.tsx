'use client'

import { useEffect } from 'react'
import { signIn } from 'next-auth/react'

export function FetchInterceptor() {
  useEffect(() => {
    // Store reference to original fetch
    const originalFetch = window.fetch

    // Override global fetch to handle 401s automatically
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const response = await originalFetch(input, init)

      // Check for 401 responses and redirect to login
      if (response.status === 401) {
        // Redirect to MediaWiki login
        signIn('wikimedia')
        throw new Error('Authentication required - redirecting to login')
      }

      return response
    }
  }, [])

  return null // This component doesn't render anything
}
