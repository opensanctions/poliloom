import { describe, it, expect, beforeEach } from 'vitest'
import {
  FILTER_LANGUAGES_COOKIE,
  FILTER_COUNTRIES_COOKIE,
  THEME_COOKIE,
  deserializeFilterCookieValue,
  readFilterCookie,
  writeFilterCookie,
  deserializeThemeCookieValue,
  readThemeCookie,
  writeThemeCookie,
} from './cookies'

function clearCookies() {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim()
    if (name) document.cookie = `${name}=; Max-Age=0; Path=/`
  }
}

// === Filter cookie tests ===

describe('deserializeFilterCookieValue', () => {
  it('returns [] for undefined or empty', () => {
    expect(deserializeFilterCookieValue(undefined)).toEqual([])
    expect(deserializeFilterCookieValue('')).toEqual([])
  })

  it('returns [] for malformed percent-encoding', () => {
    expect(deserializeFilterCookieValue('%ZZ')).toEqual([])
  })

  it('returns [] for invalid QID values', () => {
    expect(deserializeFilterCookieValue('not-valid')).toEqual([])
    expect(deserializeFilterCookieValue('42,foo')).toEqual([])
  })

  it('parses a comma-separated list of QIDs', () => {
    expect(deserializeFilterCookieValue('Q1860%2CQ7411')).toEqual(['Q1860', 'Q7411'])
  })

  it('filters invalid QIDs while keeping valid ones', () => {
    expect(deserializeFilterCookieValue('bad,Q1860,42,Q7411')).toEqual(['Q1860', 'Q7411'])
  })
})

describe('filter cookie I/O', () => {
  beforeEach(() => clearCookies())

  it('round-trips QIDs', () => {
    writeFilterCookie(FILTER_LANGUAGES_COOKIE, ['Q1860', 'Q7411'])
    expect(readFilterCookie(FILTER_LANGUAGES_COOKIE)).toEqual(['Q1860', 'Q7411'])
  })

  it('round-trips an empty array (cookie is actually present)', () => {
    writeFilterCookie(FILTER_LANGUAGES_COOKIE, [])
    expect(document.cookie).toContain(FILTER_LANGUAGES_COOKIE)
    expect(readFilterCookie(FILTER_LANGUAGES_COOKIE)).toEqual([])
  })

  it('readFilterCookie returns [] when absent', () => {
    expect(readFilterCookie(FILTER_LANGUAGES_COOKIE)).toEqual([])
  })
})

// === Theme cookie tests ===

describe('deserializeThemeCookieValue', () => {
  it('returns null for undefined', () => {
    expect(deserializeThemeCookieValue(undefined)).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(deserializeThemeCookieValue('')).toBeNull()
  })

  it('returns null for invalid values', () => {
    expect(deserializeThemeCookieValue('red')).toBeNull()
    expect(deserializeThemeCookieValue('light dark')).toBeNull()
  })

  it('returns light for light', () => {
    expect(deserializeThemeCookieValue('light')).toBe('light')
  })

  it('returns dark for dark', () => {
    expect(deserializeThemeCookieValue('dark')).toBe('dark')
  })
})

describe('theme cookie I/O', () => {
  beforeEach(() => clearCookies())

  it('round-trips light theme', () => {
    writeThemeCookie('light')
    expect(readThemeCookie()).toBe('light')
  })

  it('round-trips dark theme', () => {
    writeThemeCookie('dark')
    expect(readThemeCookie()).toBe('dark')
  })

  it('readThemeCookie returns null when absent', () => {
    expect(readThemeCookie()).toBeNull()
  })
})
