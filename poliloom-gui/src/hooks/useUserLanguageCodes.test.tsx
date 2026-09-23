import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import '@/test/mocks'
import { mockFetch, mockUseFilters, defaultFiltersContext } from '@/test/mocks'
import { useUserLanguageCodes } from './useUserLanguageCodes'
import { language, terms } from '@/test/factories'

describe('useUserLanguageCodes', () => {
  it('maps the selected language QIDs to Wikimedia codes in order', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q188', 'Q1860'],
    })
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          language(),
          language({
            wikidata_id: 'Q188',
            wikimedia_code: 'de',
            terms: terms({ en: 'German' }),
          }),
        ],
      } as Response),
    )

    const { result } = renderHook(() => useUserLanguageCodes())

    await waitFor(() => expect(result.current).toEqual(['de', 'en']))
    expect(mockFetch).toHaveBeenCalledWith('/api/languages', expect.anything())
  })

  it('skips languages without a wikimedia_code', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q1860', 'Q9999'],
    })
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          language(),
          language({
            wikidata_id: 'Q9999',
            wikimedia_code: null,
            terms: terms({ en: 'No Wikipedia' }),
          }),
        ],
      } as Response),
    )

    const { result } = renderHook(() => useUserLanguageCodes())

    await waitFor(() => expect(result.current).toEqual(['en']))
  })

  it('keeps the previous codes while fetching updated filters', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q1860'],
    })
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [language()],
      } as Response),
    )

    const { result, rerender } = renderHook(() => useUserLanguageCodes())
    await waitFor(() => expect(result.current).toEqual(['en']))

    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q188'],
    })
    rerender()

    expect(result.current).toEqual(['en'])
  })

  it('yields no codes when the request fails', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q1860'],
    })
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: false, json: async () => [] } as Response),
    )

    const { result } = renderHook(() => useUserLanguageCodes())

    await waitFor(() => expect(mockFetch).toHaveBeenCalled())
    expect(result.current).toEqual([])
  })
})
