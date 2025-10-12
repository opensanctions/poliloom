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
        // Sign out to clear the invalid session
        // This will show the logged-out home page where users can manually sign in again
        await signOut({ redirect: false })
      }

      return response
    }
  }, [])

  return null // This component doesn't render anything
}
