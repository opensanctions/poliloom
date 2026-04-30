import { cache } from 'react'
import { headers } from 'next/headers'
import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/auth'
import type { CountryResponse, LanguageResponse, User } from '@/types'

// Returns null when the caller is unauthenticated (no token, or refresh failed).
// Otherwise returns the raw backend Response — callers check `.ok` themselves.
export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response | null> {
  const session = await auth()
  if (!session?.accessToken || session.error) return null

  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${session.accessToken}`,
    },
  })
}

export function handleApiError(error: unknown, context: string) {
  console.error(`Error in ${context}:`, error)
  return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
}

export async function proxyToBackend(request: NextRequest, backendPath: string) {
  const { searchParams } = new URL(request.url)
  const queryString = searchParams.toString()
  const url = `${process.env.API_BASE_URL}${backendPath}${queryString ? `?${queryString}` : ''}`

  const requestOptions: RequestInit = { method: request.method }
  if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
    const body = await request.text()
    if (body) {
      requestOptions.body = body
      requestOptions.headers = { 'Content-Type': 'application/json' }
    }
  }

  const response = await fetchWithAuth(url, requestOptions)
  if (response === null) {
    return NextResponse.json({ message: 'Not authenticated' }, { status: 401 })
  }
  if (!response.ok) {
    return NextResponse.json(
      { message: `Backend request failed: ${response.statusText}` },
      { status: response.status },
    )
  }

  const forwardHeaders = ['content-type', 'x-accel-buffering']
  const headers = new Headers()
  for (const name of forwardHeaders) {
    const value = response.headers.get(name)
    if (value) headers.set(name, value)
  }
  return new Response(response.body, { status: response.status, headers })
}

// Server-side data fetchers used by server components / layouts.
// Each is wrapped in React's `cache()` so multiple consumers in one render
// share a single backend call.

export const getLanguages = cache(async (): Promise<LanguageResponse[]> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/languages`, {
    next: { revalidate: 3600 },
  })
  if (!res?.ok) return []
  return res.json()
})

export const getCountries = cache(async (): Promise<CountryResponse[]> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/countries`, {
    next: { revalidate: 3600 },
  })
  if (!res?.ok) return []
  return res.json()
})

// Forwards Accept-Language so the backend can seed language filters on first GET.
export const getUser = cache(async (): Promise<User | null> => {
  const incoming = await headers()
  const acceptLanguage = incoming.get('accept-language') ?? ''
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/user`, {
    headers: acceptLanguage ? { 'Accept-Language': acceptLanguage } : {},
    cache: 'no-store',
  })
  if (!res?.ok) return null
  return res.json()
})

export const getEvaluationCount = cache(async (): Promise<number | null> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/stats/count`, { cache: 'no-store' })
  if (!res?.ok) return null
  const data: { total: number } = await res.json()
  return typeof data.total === 'number' ? data.total : null
})
