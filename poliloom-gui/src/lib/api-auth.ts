import { cache } from 'react'
import { headers } from 'next/headers'
import { NextRequest, NextResponse } from 'next/server'
import type { CountryResponse, LanguageResponse, StatsResponse, UserSettings } from '@/types'

// proxy.ts is the sole caller of NextAuth's auth(). It refreshes the token
// (if needed) once per request and injects the result here. Server-side
// callers read it from this internal header — never from auth() directly.
const ACCESS_TOKEN_HEADER = 'x-access-token'

const getAccessToken = cache(async (): Promise<string> => {
  const token = (await headers()).get(ACCESS_TOKEN_HEADER)
  if (!token) {
    throw new Error(
      `Missing ${ACCESS_TOKEN_HEADER} header — proxy.ts should have injected it or rejected the request.`,
    )
  }
  return token
})

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAccessToken()
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  })
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
  if (!response.ok) {
    return NextResponse.json(
      { message: `Backend request failed: ${response.statusText}` },
      { status: response.status },
    )
  }

  const forwardHeaders = ['content-type', 'x-accel-buffering']
  const headersOut = new Headers()
  for (const name of forwardHeaders) {
    const value = response.headers.get(name)
    if (value) headersOut.set(name, value)
  }
  return new Response(response.body, { status: response.status, headers: headersOut })
}

// Server-side data fetchers used by server components / layouts.
// Each is wrapped in React's `cache()` so multiple consumers in one render
// share a single backend call. They throw on non-OK — error boundaries handle it.

export const getLanguages = cache(async (): Promise<LanguageResponse[]> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/languages`, {
    next: { revalidate: 3600 },
  })
  if (!res.ok) throw new Error(`Failed to fetch /languages: ${res.status}`)
  return res.json()
})

export const getCountries = cache(async (): Promise<CountryResponse[]> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/countries`, {
    next: { revalidate: 3600 },
  })
  if (!res.ok) throw new Error(`Failed to fetch /countries: ${res.status}`)
  return res.json()
})

export const getSettings = cache(async (): Promise<UserSettings> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/settings`, {
    cache: 'no-store',
  })
  if (!res.ok) throw new Error(`Failed to fetch /settings: ${res.status}`)
  return res.json()
})

export const getEvaluationCount = cache(async (): Promise<number> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/stats/count`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch /stats/count: ${res.status}`)
  const data: { total: number } = await res.json()
  return data.total
})

export const getStats = cache(async (): Promise<StatsResponse> => {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/stats`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch /stats: ${res.status}`)
  return res.json()
})
