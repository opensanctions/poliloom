import { describe, it, expect } from 'vitest'
import { detectAcceptLanguage } from './detectAcceptLanguage'
import type { LanguageResponse } from '@/types'

const CATALOG: LanguageResponse[] = [
  { wikidata_id: 'Q1860', name: 'English', iso_639_1: 'en', iso_639_3: 'eng', sources_count: 0 },
  { wikidata_id: 'Q7411', name: 'Dutch', iso_639_1: 'nl', iso_639_3: 'nld', sources_count: 0 },
  { wikidata_id: 'Q188', name: 'German', iso_639_1: 'de', iso_639_3: 'deu', sources_count: 0 },
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
      { wikidata_id: 'Q33', name: 'Finnish', iso_639_3: 'fin', sources_count: 0 },
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
