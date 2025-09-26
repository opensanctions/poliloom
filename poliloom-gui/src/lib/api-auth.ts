import { auth } from '@/auth'
import { NextRequest, NextResponse } from 'next/server'

export async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const session = await auth()

  if (!session?.accessToken) {
    return NextResponse.json({ message: "Not authenticated" }, { status: 401 })
  }

  if (session.error) {
    return NextResponse.json({ message: "Token refresh failed" }, { status: 401 })
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${session.accessToken}`,
    },
  })

  if (!response.ok) {
    return NextResponse.json(
      { message: `Backend request failed: ${response.statusText}` },
      { status: response.status }
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

export async function proxyToBackend(
  request: NextRequest,
  backendPath: string
) {
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000'

  // Forward query parameters
  const { searchParams } = new URL(request.url)
  const queryString = searchParams.toString()
  const url = `${apiBaseUrl}${backendPath}${queryString ? `?${queryString}` : ''}`

  // Prepare request options
  const requestOptions: RequestInit = {
    method: request.method,
  }

  // Forward body for POST/PUT/PATCH requests
  if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
    const body = await request.text()
    if (body) {
      requestOptions.body = body
      requestOptions.headers = {
        'Content-Type': 'application/json',
      }
    }
  }

  const response = await fetchWithAuth(url, requestOptions)

  // If fetchWithAuth returned an error response, return it directly
  if (response instanceof NextResponse) {
    return response
  }

  const data = await response.json()
  return NextResponse.json(data)
}