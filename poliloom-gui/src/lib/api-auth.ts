import { auth } from '@/auth'
import { NextResponse } from 'next/server'

export async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const session = await auth()
  
  if (!session?.accessToken) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // If session has an error (like RefreshAccessTokenError), return 401
  if (session.error) {
    return NextResponse.json({ error: 'Token refresh failed' }, { status: 401 })
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${session.accessToken}`,
    },
  })

  // If we get a 401 from the backend, the token might have expired
  // between our session check and the API call. The client will need to
  // handle this by refreshing the page or making a new request.
  if (response.status === 401) {
    return NextResponse.json(
      { error: 'Backend authentication failed. Please refresh and try again.' },
      { status: 401 }
    )
  }

  return response
}

export function handleApiError(error: unknown, context: string) {
  console.error(`Error in ${context}:`, error)
  return NextResponse.json(
    { error: 'Internal server error' },
    { status: 500 }
  )
}