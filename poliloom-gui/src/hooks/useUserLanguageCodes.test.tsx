import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import '@/test/mocks'
import { mockFetch, mockUseFilters, defaultFiltersContext } from '@/test/mocks'
import { useUserLanguageCodes } from './useUserLanguageCodes'
import type { LanguageResponse } from '@/types'

const language = (
  wikidata_id: string,
  wikimedia_code: string | null,
  label: string,
): LanguageResponse => ({
  wikidata_id,
  terms: { labels: { en: label }, descriptions: {}, aliases: {} },
  wikimedia_code,
  sources_count: 0,
})

describe('useUserLanguageCodes', () => {
  it('maps the selected language QIDs to Wikimedia codes in order', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q188', 'Q1860'],
    })
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [language('Q1860', 'en', 'English'), language('Q188', 'de', 'German')],
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
          language('Q1860', 'en', 'English'),
          language('Q9999', null, 'No Wikipedia'),
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
        json: async () => [language('Q1860', 'en', 'English')],
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
