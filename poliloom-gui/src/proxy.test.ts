// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextRequest, NextResponse } from 'next/server'

type MockAuth = {
  accessToken?: string
  error?: string
  hasWikidataAccount?: boolean
} | null

let mockAuthValue: MockAuth = null

vi.mock('@/auth', () => ({
  auth: (fn: (req: NextRequest & { auth: MockAuth }) => NextResponse) => (req: NextRequest) => {
    const r = req as NextRequest & { auth: MockAuth }
    r.auth = mockAuthValue
    return fn(r)
  },
}))

import { applyFilterCookies } from './proxy'
import middleware, { config } from './proxy'

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365

function createRequest(url: string, headers?: Record<string, string>) {
  return new NextRequest(url, headers ? { headers } : undefined)
}

function callMiddleware(url: string, headers?: Record<string, string>) {
  const request = createRequest(url, headers)
  return (middleware as unknown as (req: NextRequest) => NextResponse)(request)
}

beforeEach(() => {
  mockAuthValue = { accessToken: 'tok', hasWikidataAccount: true }
})

describe('filter cookies', () => {
  it('sets language cookie from URL query param', () => {
    const request = createRequest('http://localhost:3000/?languages=Q1860')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_languages')?.value).toBe('Q1860')
  })

  it('sets country cookie from URL query param', () => {
    const request = createRequest('http://localhost:3000/?countries=Q30')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_countries')?.value).toBe('Q30')
  })

  it('sets both cookies when both params present', () => {
    const request = createRequest('http://localhost:3000/?languages=Q1860&countries=Q30')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_languages')?.value).toBe('Q1860')
    expect(response.cookies.get('poliloom_filter_countries')?.value).toBe('Q30')
  })

  it('handles repeated keys', () => {
    const request = createRequest('http://localhost:3000/?languages=Q1860&languages=Q7411')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_languages')?.value).toBe('Q1860%2CQ7411')
  })

  it('writes empty array for empty param', () => {
    const request = createRequest('http://localhost:3000/?languages=')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_languages')?.value).toBe('')
  })

  it('does not touch absent cookie', () => {
    const request = createRequest('http://localhost:3000/?languages=Q1860')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_countries')).toBeUndefined()
  })

  it('works on non-root routes', () => {
    const request = createRequest('http://localhost:3000/politician/Q123?languages=Q1860')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_languages')?.value).toBe('Q1860')
  })

  it('no-ops when no filter params present', () => {
    const request = createRequest('http://localhost:3000/')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    expect(response.cookies.get('poliloom_filter_languages')).toBeUndefined()
    expect(response.cookies.get('poliloom_filter_countries')).toBeUndefined()
  })

  it('sets response cookie with correct attributes', () => {
    const request = createRequest('http://localhost:3000/?languages=Q1860')
    const response = NextResponse.next()
    applyFilterCookies(request, response)

    const setCookie = response.headers.get('set-cookie')
    expect(setCookie).toContain('Path=/')
    expect(setCookie).toContain('SameSite=lax')
    expect(setCookie).toContain(`Max-Age=${ONE_YEAR_SECONDS}`)
    expect(setCookie).toContain(encodeURIComponent('Q1860'))
  })
})

describe('middleware filter param stripping', () => {
  it('redirects to clean URL when filter params present', () => {
    const response = callMiddleware('http://localhost:3000/?countries=Q30')
    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toBe('http://localhost:3000/')
  })

  it('preserves non-filter query params', () => {
    const response = callMiddleware('http://localhost:3000/?countries=Q30&foo=bar')
    expect(response.headers.get('location')).toBe('http://localhost:3000/?foo=bar')
  })

  it('redirects on non-root routes', () => {
    const response = callMiddleware('http://localhost:3000/politician/Q123?languages=Q1860')
    expect(response.headers.get('location')).toBe('http://localhost:3000/politician/Q123')
  })

  it('does not redirect when no filter params present', () => {
    const response = callMiddleware('http://localhost:3000/')
    expect(response.status).not.toBe(307)
  })

  it('does not strip filter params on /api/* routes', () => {
    const response = callMiddleware(
      'http://localhost:3000/api/politicians/next?languages=Q1860&countries=Q30',
    )
    expect(response.status).not.toBe(307)
  })
})

describe('middleware auth gating', () => {
  describe('unauthenticated', () => {
    beforeEach(() => {
      mockAuthValue = null
    })

    it('redirects pages to /login with redirect param', () => {
      const response = callMiddleware('http://localhost:3000/politician/Q123')
      expect(response.status).toBe(307)
      const location = response.headers.get('location')
      expect(location).toMatch(/\/login\?redirect=/)
      expect(location).toContain(encodeURIComponent('/politician/Q123'))
    })

    it('returns 401 JSON for /api/* routes (no redirect)', async () => {
      const response = callMiddleware('http://localhost:3000/api/stats')
      expect(response.status).toBe(401)
      expect(response.headers.get('content-type')).toMatch(/json/)
      const body = await response.json()
      expect(body).toEqual({ message: 'Not authenticated' })
    })

    it('does not redirect /login itself', () => {
      const response = callMiddleware('http://localhost:3000/login')
      expect(response.status).not.toBe(307)
    })
  })

  describe('authenticated with refresh error', () => {
    beforeEach(() => {
      mockAuthValue = { accessToken: 'stale', error: 'RefreshAccessTokenError' }
    })

    it('treats error as unauthenticated and redirects pages to /login', () => {
      const response = callMiddleware('http://localhost:3000/')
      expect(response.status).toBe(307)
      expect(response.headers.get('location')).toMatch(/\/login/)
    })

    it('returns 401 JSON for /api/* routes', () => {
      const response = callMiddleware('http://localhost:3000/api/stats')
      expect(response.status).toBe(401)
    })
  })

  describe('authenticated hitting /login', () => {
    it('redirects to / by default', () => {
      const response = callMiddleware('http://localhost:3000/login')
      expect(response.status).toBe(307)
      expect(response.headers.get('location')).toBe('http://localhost:3000/')
    })

    it('honors the redirect query param', () => {
      const response = callMiddleware('http://localhost:3000/login?redirect=/politician/Q1')
      expect(response.headers.get('location')).toBe('http://localhost:3000/politician/Q1')
    })
  })

  describe('authenticated without Wikidata account', () => {
    beforeEach(() => {
      mockAuthValue = { accessToken: 'tok', hasWikidataAccount: false }
    })

    it('redirects pages to /setup', () => {
      const response = callMiddleware('http://localhost:3000/')
      expect(response.status).toBe(307)
      expect(response.headers.get('location')).toBe('http://localhost:3000/setup')
    })

    it('returns 403 JSON for /api/* routes', async () => {
      const response = callMiddleware('http://localhost:3000/api/stats')
      expect(response.status).toBe(403)
      const body = await response.json()
      expect(body).toEqual({ message: 'Wikidata account required' })
    })

    it('does not redirect /setup itself', () => {
      const response = callMiddleware('http://localhost:3000/setup')
      expect(response.status).not.toBe(307)
    })
  })
})

describe('middleware access token injection', () => {
  it('injects x-access-token into the forwarded request', () => {
    const response = callMiddleware('http://localhost:3000/')
    const forwarded = response.headers.get('x-middleware-request-x-access-token')
    expect(forwarded).toBe('tok')
  })

  it('strips a client-supplied x-access-token before injecting', () => {
    const response = callMiddleware('http://localhost:3000/', {
      'x-access-token': 'spoofed-by-client',
    })
    const forwarded = response.headers.get('x-middleware-request-x-access-token')
    expect(forwarded).toBe('tok')
  })

  it('does not inject when unauthenticated', () => {
    mockAuthValue = null
    const response = callMiddleware('http://localhost:3000/login')
    expect(response.headers.get('x-middleware-request-x-access-token')).toBeNull()
  })
})

describe('middleware matcher', () => {
  const matcher = new RegExp(`^${config.matcher[0]}$`)

  it('skips NextAuth internal routes', () => {
    expect(matcher.test('/api/auth/callback')).toBe(false)
    expect(matcher.test('/api/auth/session')).toBe(false)
  })

  it('skips Next.js internals and favicon', () => {
    expect(matcher.test('/_next/static/chunks/main.js')).toBe(false)
    expect(matcher.test('/_next/image')).toBe(false)
    expect(matcher.test('/favicon.ico')).toBe(false)
  })

  it('runs on user-facing routes', () => {
    expect(matcher.test('/')).toBe(true)
    expect(matcher.test('/politician/Q123')).toBe(true)
    expect(matcher.test('/login')).toBe(true)
  })

  it('runs on /api/* routes (excluding /api/auth)', () => {
    expect(matcher.test('/api/politicians/next')).toBe(true)
    expect(matcher.test('/api/entities/search')).toBe(true)
    expect(matcher.test('/api/stats')).toBe(true)
  })
})
