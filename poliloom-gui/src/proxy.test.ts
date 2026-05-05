// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { NextRequest, NextResponse } from 'next/server'

vi.mock('@/auth', () => ({
  auth: (fn: any) => fn,
}))

import { applyFilterCookies } from './proxy'

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
