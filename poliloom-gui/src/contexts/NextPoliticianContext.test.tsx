import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { NextPoliticianProvider, useNextPoliticianContext } from './NextPoliticianContext'
import { EventStreamProvider } from './EventStreamContext'
import { mockEventSource } from '@/test/setup'
import type { SSEEvent, NextPoliticianResponse, User, WikidataEntity } from '@/types'

const DEFAULT_USER: User = {
  settings: {
    advanced_mode: false,
    basic_tutorial_completed: true,
    advanced_tutorial_completed: true,
    stats_unlocked: false,
  },
  filters: { language: [], country: [] },
}

let mockUser: User | null | undefined = DEFAULT_USER
let mockPending = false

vi.mock('@/contexts/UserContext', () => ({
  useUser: () => ({
    user: mockUser,
    pending: mockPending,
    patch: vi.fn(),
  }),
}))

let mockParams: Record<string, string> = {}
vi.mock('next/navigation', () => ({
  useParams: () => mockParams,
}))

function setUser(filters: Partial<User['filters']> = {}) {
  mockUser = {
    ...DEFAULT_USER,
    filters: {
      language: filters.language ?? [],
      country: filters.country ?? [],
    },
  }
}

function entity(qid: string, name: string): WikidataEntity {
  return { wikidata_id: qid, name }
}

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
    setUser()
    mockPending = false
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

  it('does not pass language or country filters as query params (server reads them)', async () => {
    setUser({
      language: [entity('Q1860', 'English')],
      country: [entity('Q30', 'United States')],
    })

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => nextResponse,
    } as Response)

    renderHook(() => useNextPoliticianContext(), { wrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })

    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string
    expect(calledUrl).not.toContain('languages=')
    expect(calledUrl).not.toContain('countries=')
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

  it('does not fetch while user is loading (undefined)', () => {
    mockUser = undefined
    renderHook(() => useNextPoliticianContext(), { wrapper })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('does not fetch while a PATCH is in flight (pending=true)', () => {
    mockPending = true
    renderHook(() => useNextPoliticianContext(), { wrapper })
    expect(fetch).not.toHaveBeenCalled()
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

  it('throws when used outside provider', () => {
    expect(() => {
      renderHook(() => useNextPoliticianContext())
    }).toThrow('useNextPoliticianContext must be used within a NextPoliticianProvider')
  })
})
