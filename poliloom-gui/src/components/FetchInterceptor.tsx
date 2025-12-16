'use client'

import { useEffect } from 'react'
import { signOut } from 'next-auth/react'

export function FetchInterceptor() {
  useEffect(() => {
    // Store reference to original fetch
    const originalFetch = window.fetch

    // Override global fetch to handle 401s automatically
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const response = await originalFetch(input, init)

      // Check for 401 responses and sign out to clear invalid session
      if (response.status === 401) {
        await signOut({ callbackUrl: '/login' })
      }

      return response
    }
  }, [])

  return null // This component doesn't render anything
}
