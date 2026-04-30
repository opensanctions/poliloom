import { describe, it, expect, beforeEach } from 'vitest'
import {
  FILTER_LANGUAGES_COOKIE,
  parseFilterCookieValue,
  readFilterCookie,
  writeFilterCookie,
} from './filterCookies'

function clearCookies() {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim()
    if (name) document.cookie = `${name}=; Max-Age=0; Path=/`
  }
}

describe('parseFilterCookieValue', () => {
  it('returns [] for undefined or empty', () => {
    expect(parseFilterCookieValue(undefined)).toEqual([])
    expect(parseFilterCookieValue('')).toEqual([])
  })

  it('returns [] for malformed JSON', () => {
    expect(parseFilterCookieValue('not-json')).toEqual([])
    expect(parseFilterCookieValue('{"a":1}')).toEqual([])
  })

  it('parses a JSON array of strings', () => {
    expect(parseFilterCookieValue('["Q1860","Q7411"]')).toEqual(['Q1860', 'Q7411'])
  })

  it('filters non-string entries', () => {
    expect(parseFilterCookieValue('["Q1860",42,null,"Q7411"]')).toEqual(['Q1860', 'Q7411'])
  })
})

describe('cookie I/O', () => {
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
