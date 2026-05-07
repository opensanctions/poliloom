// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { NextRequest, NextResponse } from 'next/server'

vi.mock('@/auth', () => ({
  auth: (fn: any) => (req: any) => {
    req.auth = { hasWikidataAccount: true }
    return fn(req)
  },
}))

import { applyFilterCookies } from './proxy'
import middleware, { config } from './proxy'

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365

function createRequest(url: string) {
  return new NextRequest(url)
}

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

describe('middleware URL rewriting', () => {
  function callMiddleware(url: string) {
    const request = createRequest(url)
    return (middleware as any)(request) as NextResponse
  }

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
})

describe('middleware matcher', () => {
  const matcher = new RegExp(`^${config.matcher[0]}$`)

  it('skips /api/* routes so filter params reach the proxy untouched', () => {
    expect(matcher.test('/api/politicians/next')).toBe(false)
    expect(matcher.test('/api/auth/callback')).toBe(false)
    expect(matcher.test('/api/entities/search')).toBe(false)
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
})
