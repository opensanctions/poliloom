import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { NextPoliticianProvider, useNextPoliticianContext } from './NextPoliticianContext'
import { EventStreamProvider } from './EventStreamContext'
import { mockEventSource } from '@/test/setup'
import { PreferenceType } from '@/types'
import type { SSEEvent, NextPoliticianResponse } from '@/types'

let mockFilters: Array<{ wikidata_id: string; name: string; preference_type: PreferenceType }> = []
vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    filters: mockFilters,
  }),
}))

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <EventStreamProvider>
      <NextPoliticianProvider>{children}</NextPoliticianProvider>
    </EventStreamProvider>
  )
}

const nextResponse: NextPoliticianResponse = {
  wikidata_id: 'Q12345',
  meta: { has_enrichable_politicians: true, total_matching_filters: 10 },
}

describe('NextPoliticianContext', () => {
  beforeEach(() => {
    mockFilters = []
  })

  it('fetches next politician on mount', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    const { result } = renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(result.current.politicianReady).toBe(true)
    })

    expect(result.current.nextHref).toBe('/politician/Q12345')
    expect(result.current.loading).toBe(false)
    expect(result.current.allCaughtUp).toBe(false)
  })

  it('passes language and country filters as query params', async () => {
    mockFilters = [
      { wikidata_id: 'Q1860', name: 'English', preference_type: PreferenceType.LANGUAGE },
      { wikidata_id: 'Q30', name: 'United States', preference_type: PreferenceType.COUNTRY },
    ]

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })

    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string
    expect(calledUrl).toContain('languages=Q1860')
    expect(calledUrl).toContain('countries=Q30')
  })

  it('advanceNext fetches a new politician excluding the current one', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => nextResponse,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          wikidata_id: 'Q67890',
          meta: { has_enrichable_politicians: true, total_matching_filters: 9 },
        }),
      } as Response)

    const { result } = renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(result.current.politicianReady).toBe(true)
    })

    await act(async () => {
      result.current.advanceNext()
    })

    await waitFor(() => {
      expect(result.current.politicianReady).toBe(true)
    })

    const secondUrl = vi.mocked(fetch).mock.calls[1][0] as string
    expect(secondUrl).toContain('exclude_ids=Q12345')
  })

  it('ignores enrichment_complete event when politician is already ready', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledTimes(1)
    })

    const event: SSEEvent = {
      type: 'enrichment_complete',
      languages: ['Q1860'],
      countries: ['Q30'],
    }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('fetches on enrichment_complete event when no politician is ready', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        wikidata_id: null,
        meta: { has_enrichable_politicians: false, total_matching_filters: 0 },
      }),
    } as Response)

    const { result } = renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.politicianReady).toBe(false)

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    const event: SSEEvent = {
      type: 'enrichment_complete',
      languages: ['Q1860'],
      countries: ['Q30'],
    }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    await waitFor(() => {
      expect(result.current.politicianReady).toBe(true)
    })
  })

  it('ignores enrichment_complete event when language filter does not match', async () => {
    mockFilters = [
      { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
    ]

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        wikidata_id: null,
        meta: { has_enrichable_politicians: false, total_matching_filters: 0 },
      }),
    } as Response)

    const { result } = renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const event: SSEEvent = {
      type: 'enrichment_complete',
      languages: ['Q1860'],
      countries: [],
    }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('fetches on enrichment_complete when event matches language filter', async () => {
    mockFilters = [
      { wikidata_id: 'Q1860', name: 'English', preference_type: PreferenceType.LANGUAGE },
    ]

    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          wikidata_id: null,
          meta: { has_enrichable_politicians: false, total_matching_filters: 0 },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => nextResponse,
      } as Response)

    const { result } = renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const event: SSEEvent = {
      type: 'enrichment_complete',
      languages: ['Q1860'],
      countries: ['Q30'],
    }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    await waitFor(() => {
      expect(result.current.politicianReady).toBe(true)
    })
  })

  it('ignores enrichment_complete event when country filter does not match', async () => {
    mockFilters = [{ wikidata_id: 'Q142', name: 'France', preference_type: PreferenceType.COUNTRY }]

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        wikidata_id: null,
        meta: { has_enrichable_politicians: false, total_matching_filters: 0 },
      }),
    } as Response)

    const { result } = renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const event: SSEEvent = {
      type: 'enrichment_complete',
      languages: [],
      countries: ['Q30'],
    }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('throws when used outside provider', () => {
    expect(() => {
      renderHook(() => useNextPoliticianContext())
    }).toThrow('useNextPoliticianContext must be used within a NextPoliticianProvider')
  })
})
