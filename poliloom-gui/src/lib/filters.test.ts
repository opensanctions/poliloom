import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { getCountries, getLanguages } from '@/lib/api-auth'
import { country, language, terms } from '@/test/factories'

const mockCookiesGet = vi.fn()
const mockHeadersGet = vi.fn()
vi.mock('next/headers', () => ({
  cookies: vi.fn(() => Promise.resolve({ get: mockCookiesGet })),
  headers: vi.fn(() => Promise.resolve({ get: mockHeadersGet })),
}))

const mockGetLanguages = vi.fn<typeof getLanguages>()
const mockGetCountries = vi.fn<typeof getCountries>()
vi.mock('@/lib/api-auth', () => ({
  getLanguages: () => mockGetLanguages(),
  getCountries: () => mockGetCountries(),
}))

import { resolveLanguageQids, getFilterCountryQids } from './filters'

beforeEach(() => {
  mockCookiesGet.mockReset()
  mockHeadersGet.mockReset()
  mockGetLanguages.mockReset()
  mockGetCountries.mockReset()
})

describe('resolveLanguageQids', () => {
  const languages = [
    language(),
    language({ wikidata_id: 'Q7411', terms: terms({ en: 'Dutch' }), iso_639_1: 'nl' }),
  ]

  it('returns valid QIDs from the cookie without autodetecting', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q1860%2CQREMOVED' })
    mockGetLanguages.mockResolvedValue(languages)

    await expect(resolveLanguageQids()).resolves.toEqual(['Q1860'])
    expect(mockHeadersGet).not.toHaveBeenCalled()
  })

  it('autodetects languages when the cookie has no valid QIDs', async () => {
    mockCookiesGet.mockReturnValue({ value: 'QREMOVED' })
    mockHeadersGet.mockReturnValue('nl-NL,en;q=0.5')
    mockGetLanguages.mockResolvedValue(languages)

    await expect(resolveLanguageQids()).resolves.toEqual(['Q7411', 'Q1860'])
  })

  it('falls back to English when no language can be detected', async () => {
    mockCookiesGet.mockReturnValue(undefined)
    mockHeadersGet.mockReturnValue('xx-XX')
    mockGetLanguages.mockResolvedValue(languages)

    await expect(resolveLanguageQids()).resolves.toEqual(['Q1860'])
  })
})

describe('getFilterCountryQids', () => {
  it('returns [] when no cookie is set, without calling the API', async () => {
    mockCookiesGet.mockReturnValue(undefined)

    const result = await getFilterCountryQids()

    expect(result).toEqual([])
    expect(mockGetCountries).not.toHaveBeenCalled()
  })

  it('returns [] when cookie is present but empty', async () => {
    mockCookiesGet.mockReturnValue({ value: '' })
    mockGetCountries.mockResolvedValue([country()])

    const result = await getFilterCountryQids()

    expect(result).toEqual([])
  })

  it('returns QIDs that exist in the API', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q30%2CQ183' })
    mockGetCountries.mockResolvedValue([
      country(),
      country({ wikidata_id: 'Q183', terms: terms({ en: 'Germany' }) }),
      country({ wikidata_id: 'Q142', terms: terms({ en: 'France' }) }),
    ])

    const result = await getFilterCountryQids()

    expect(result).toEqual(['Q30', 'Q183'])
  })

  it('filters out stale QIDs no longer in the API', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q30%2CQREMOVED' })
    mockGetCountries.mockResolvedValue([country()])

    const result = await getFilterCountryQids()

    expect(result).toEqual(['Q30'])
  })

  it('returns [] when all QIDs are stale', async () => {
    mockCookiesGet.mockReturnValue({ value: 'QSTALE1%2CQSTALE2' })
    mockGetCountries.mockResolvedValue([country()])

    const result = await getFilterCountryQids()

    expect(result).toEqual([])
  })
})
