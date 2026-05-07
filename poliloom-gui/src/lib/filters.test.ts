import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockCookiesGet = vi.fn()
vi.mock('next/headers', () => ({
  cookies: vi.fn(() => Promise.resolve({ get: mockCookiesGet })),
}))

const mockGetLanguages = vi.fn()
const mockGetCountries = vi.fn()
vi.mock('@/lib/api-auth', () => ({
  getLanguages: () => mockGetLanguages(),
  getCountries: () => mockGetCountries(),
}))

import { getFilterLanguageQids, getFilterCountryQids } from './filters'

beforeEach(() => {
  mockCookiesGet.mockReset()
  mockGetLanguages.mockReset()
  mockGetCountries.mockReset()
})

describe('getFilterLanguageQids', () => {
  it('returns null when no cookie is set', async () => {
    mockCookiesGet.mockReturnValue(undefined)

    const result = await getFilterLanguageQids()

    expect(result).toBeNull()
    expect(mockGetLanguages).not.toHaveBeenCalled()
  })

  it('returns [] when cookie is present but empty', async () => {
    mockCookiesGet.mockReturnValue({ value: '' })
    mockGetLanguages.mockResolvedValue([{ wikidata_id: 'Q1860', label: 'English' }])

    const result = await getFilterLanguageQids()

    expect(result).toEqual([])
  })

  it('returns QIDs that exist in the API', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q1860%2CQ7411' })
    mockGetLanguages.mockResolvedValue([
      { wikidata_id: 'Q1860', label: 'English' },
      { wikidata_id: 'Q7411', label: 'Dutch' },
      { wikidata_id: 'Q150', label: 'French' },
    ])

    const result = await getFilterLanguageQids()

    expect(result).toEqual(['Q1860', 'Q7411'])
  })

  it('filters out stale QIDs no longer in the API', async () => {
    mockCookiesGet.mockReturnValue({ value: 'Q1860%2CQREMOVED' })
    mockGetLanguages.mockResolvedValue([{ wikidata_id: 'Q1860', label: 'English' }])

    const result = await getFilterLanguageQids()

    expect(result).toEqual(['Q1860'])
  })

  it('returns [] when all QIDs are stale', async () => {
    mockCookiesGet.mockReturnValue({ value: 'QSTALE1%2CQSTALE2' })
    mockGetLanguages.mockResolvedValue([{ wikidata_id: 'Q1860', label: 'English' }])

    const result = await getFilterLanguageQids()

    expect(result).toEqual([])
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
