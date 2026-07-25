import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockCookiesGet = vi.fn()
const mockHeadersGet = vi.fn()
vi.mock('next/headers', () => ({
  cookies: vi.fn(() => Promise.resolve({ get: mockCookiesGet })),
  headers: vi.fn(() => Promise.resolve({ get: mockHeadersGet })),
}))

const mockGetLanguages = vi.fn()
const mockGetCountries = vi.fn()
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
    { wikidata_id: 'Q1860', name: 'English', iso_639_1: 'en' },
    { wikidata_id: 'Q7411', name: 'Dutch', iso_639_1: 'nl' },
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
    mockGetCountries.mockResolvedValue([{ wikidata_id: 'Q30', label: 'United States' }])

    const result = await getFilterCountryQids()

    expect(result).toEqual([])
  })

  it('returns QIDs that exist in the API', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q30%2CQ183' })
    mockGetCountries.mockResolvedValue([
      { wikidata_id: 'Q30', label: 'United States' },
      { wikidata_id: 'Q183', label: 'Germany' },
      { wikidata_id: 'Q142', label: 'France' },
    ])

    const result = await getFilterCountryQids()

    expect(result).toEqual(['Q30', 'Q183'])
  })

  it('filters out stale QIDs no longer in the API', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q30%2CQREMOVED' })
    mockGetCountries.mockResolvedValue([{ wikidata_id: 'Q30', label: 'United States' }])

    const result = await getFilterCountryQids()

    expect(result).toEqual(['Q30'])
  })

  it('returns [] when all QIDs are stale', async () => {
    mockCookiesGet.mockReturnValue({ value: 'QSTALE1%2CQSTALE2' })
    mockGetCountries.mockResolvedValue([{ wikidata_id: 'Q30', label: 'United States' }])

    const result = await getFilterCountryQids()

    expect(result).toEqual([])
  })
})
