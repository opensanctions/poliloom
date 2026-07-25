import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { NextPoliticianProvider, useNextPoliticianContext } from './NextPoliticianContext'
import { EventStreamProvider } from './EventStreamContext'
import { mockEventSource } from '@/test/setup'
import type { SSEEvent, NextPoliticianResponse } from '@/types'

let mockLanguageQids: string[] = []
let mockCountryQids: string[] = []

vi.mock('@/contexts/FilterContext', () => ({
  useFilters: () => ({
    languageQids: mockLanguageQids,
    countryQids: mockCountryQids,
    setLanguages: vi.fn(),
    setCountries: vi.fn(),
  }),
}))

let mockParams: Record<string, string> = {}
vi.mock('next/navigation', () => ({
  useParams: () => mockParams,
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
  meta: { has_enrichable_politicians: true },
}

describe('NextPoliticianContext', () => {
  beforeEach(() => {
    mockLanguageQids = []
    mockCountryQids = []
    mockParams = {}
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

  it('passes language and country filter QIDs as query params', async () => {
    mockLanguageQids = ['Q1860']
    mockCountryQids = ['Q30']

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

  it('reports loading while refetching after filters change', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    let resolveResponse!: (response: Response) => void
    vi.mocked(fetch).mockImplementationOnce(
      () => new Promise((resolve) => (resolveResponse = resolve)),
    )

    const { result, rerender } = renderHook(() => useNextPoliticianContext(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    mockLanguageQids = ['Q1860']
    rerender()

    expect(result.current.loading).toBe(true)
    resolveResponse({
      ok: true,
      json: async () => nextResponse,
    } as Response)
    await waitFor(() => expect(result.current.loading).toBe(false))
  })

  it('excludes current politician from route params', async () => {
    mockParams = { qid: 'Q99999' }

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })

    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string
    expect(calledUrl).toContain('exclude_ids=Q99999')
  })

  it('does not exclude when not on a politician route', async () => {
    mockParams = {}

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })

    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string
    expect(calledUrl).not.toContain('exclude_ids')
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
        meta: { has_enrichable_politicians: false },
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

  it('throws when used outside provider', () => {
    expect(() => {
      renderHook(() => useNextPoliticianContext())
    }).toThrow('useNextPoliticianContext must be used within a NextPoliticianProvider')
  })
})
