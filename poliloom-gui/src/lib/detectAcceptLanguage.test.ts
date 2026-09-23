import { describe, it, expect } from 'vitest'
import { detectAcceptLanguage } from './detectAcceptLanguage'
import { language, terms } from '@/test/factories'
import type { LanguageResponse } from '@/types'

const CATALOG: LanguageResponse[] = [
  language(),
  language({
    wikidata_id: 'Q7411',
    terms: terms({ en: 'Dutch' }),
    iso_639_1: 'nl',
    iso_639_3: 'nld',
  }),
  language({
    wikidata_id: 'Q188',
    terms: terms({ en: 'German' }),
    iso_639_1: 'de',
    iso_639_3: 'deu',
  }),
]

describe('detectAcceptLanguage', () => {
  it('returns [] for null, empty, or wildcard-only headers', () => {
    expect(detectAcceptLanguage(null, CATALOG)).toEqual([])
    expect(detectAcceptLanguage('', CATALOG)).toEqual([])
    expect(detectAcceptLanguage('*', CATALOG)).toEqual([])
  })

  it('matches by ISO 639-1 in header order when q is absent', () => {
    expect(detectAcceptLanguage('nl-NL,en-US,de', CATALOG)).toEqual(['Q7411', 'Q1860', 'Q188'])
  })

  it('orders by descending q-value', () => {
    expect(detectAcceptLanguage('en;q=0.5,nl;q=0.9,de;q=0.7', CATALOG)).toEqual([
      'Q7411',
      'Q188',
      'Q1860',
    ])
  })

  it('treats missing q as 1.0 (highest priority)', () => {
    expect(detectAcceptLanguage('en;q=0.5,nl', CATALOG)).toEqual(['Q7411', 'Q1860'])
  })

  it('falls back to ISO 639-3 when 639-1 absent', () => {
    const catalog: LanguageResponse[] = [
      language({
        wikidata_id: 'Q33',
        terms: terms({ en: 'Finnish' }),
        wikimedia_code: null,
        iso_639_1: undefined,
        iso_639_3: 'fin',
      }),
    ]
    expect(detectAcceptLanguage('fin-FI', catalog)).toEqual(['Q33'])
  })

  it('dedupes when multiple header entries map to the same QID', () => {
    expect(detectAcceptLanguage('en-US,en-GB,en', CATALOG)).toEqual(['Q1860'])
  })

  it('skips unknown codes', () => {
    expect(detectAcceptLanguage('xx,en', CATALOG)).toEqual(['Q1860'])
  })

  it('skips wildcard entries mixed with real codes', () => {
    expect(detectAcceptLanguage('nl,*;q=0.1', CATALOG)).toEqual(['Q7411'])
  })

  it('returns [] when no codes match the catalog', () => {
    expect(detectAcceptLanguage('xx,yy', CATALOG)).toEqual([])
  })
})
