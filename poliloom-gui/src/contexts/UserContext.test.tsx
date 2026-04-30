import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useSession } from 'next-auth/react'
import { UserProvider, useUser } from './UserContext'
import type { User } from '@/types'

function wrapper({ children }: { children: React.ReactNode }) {
  return <UserProvider>{children}</UserProvider>
}

const POPULATED: User = {
  settings: {
    advanced_mode: false,
    basic_tutorial_completed: false,
    advanced_tutorial_completed: false,
    stats_unlocked: false,
  },
  filters: {
    language: [{ wikidata_id: 'Q1860', name: 'English' }],
    country: [],
  },
}

function mockGet(value: User | null) {
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: true,
    json: async () => value,
  } as Response)
}

function mockPatchOk() {
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: true,
    json: async () => POPULATED,
  } as Response)
}

function mockPatchFail() {
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: false,
    status: 500,
    json: async () => ({}),
  } as Response)
}

describe('UserContext', () => {
  it('does not fetch when unauthenticated', () => {
    vi.mocked(useSession).mockReturnValue({
      data: null,
      status: 'unauthenticated',
      update: vi.fn(),
    })
    const { result } = renderHook(() => useUser(), { wrapper })
    expect(result.current.user).toBeUndefined()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('fetches on mount when authenticated and stores null for first login', async () => {
    mockGet(null)
    const { result } = renderHook(() => useUser(), { wrapper })
    await waitFor(() => {
      expect(result.current.user).toBeNull()
    })
    expect(fetch).toHaveBeenCalledWith('/api/user')
  })

  it('fetches on mount and stores populated user', async () => {
    mockGet(POPULATED)
    const { result } = renderHook(() => useUser(), { wrapper })
    await waitFor(() => {
      expect(result.current.user).toEqual(POPULATED)
    })
  })

  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useUser())).toThrow('useUser must be used within a UserProvider')
  })

  describe('patch', () => {
    it('optimistically merges settings and serializes empty wire payload for filters', async () => {
      mockGet(POPULATED)
      const { result } = renderHook(() => useUser(), { wrapper })
      await waitFor(() => expect(result.current.user).toEqual(POPULATED))

      mockPatchOk()
      await act(async () => {
        await result.current.patch({ settings: { advanced_mode: true } })
      })

      expect(result.current.user?.settings.advanced_mode).toBe(true)
      // filters reference preserved (settings-only patch)
      expect(result.current.user?.filters).toBe(POPULATED.filters)

      const [, init] = vi.mocked(fetch).mock.calls.at(-1)!
      expect(JSON.parse((init as RequestInit).body as string)).toEqual({
        settings: { advanced_mode: true },
      })
    })

    it('serializes filter entities to QID arrays on the wire', async () => {
      mockGet(POPULATED)
      const { result } = renderHook(() => useUser(), { wrapper })
      await waitFor(() => expect(result.current.user).toEqual(POPULATED))

      mockPatchOk()
      await act(async () => {
        await result.current.patch({
          filters: { country: [{ wikidata_id: 'Q30', name: 'United States' }] },
        })
      })

      const [, init] = vi.mocked(fetch).mock.calls.at(-1)!
      expect(JSON.parse((init as RequestInit).body as string)).toEqual({
        filters: { country: ['Q30'] },
      })
      expect(result.current.user?.filters.country).toEqual([
        { wikidata_id: 'Q30', name: 'United States' },
      ])
      // language untouched
      expect(result.current.user?.filters.language).toEqual(POPULATED.filters.language)
    })

    it('builds default User when patching from null (first-login case)', async () => {
      mockGet(null)
      const { result } = renderHook(() => useUser(), { wrapper })
      await waitFor(() => expect(result.current.user).toBeNull())

      mockPatchOk()
      await act(async () => {
        await result.current.patch({
          filters: { language: [{ wikidata_id: 'Q1860', name: 'English' }] },
        })
      })

      expect(result.current.user).toEqual({
        settings: {
          advanced_mode: false,
          basic_tutorial_completed: false,
          advanced_tutorial_completed: false,
          stats_unlocked: false,
        },
        filters: {
          language: [{ wikidata_id: 'Q1860', name: 'English' }],
          country: [],
        },
      })
    })

    it('reverts to snapshot on PATCH failure', async () => {
      mockGet(POPULATED)
      const { result } = renderHook(() => useUser(), { wrapper })
      await waitFor(() => expect(result.current.user).toEqual(POPULATED))

      mockPatchFail()
      await act(async () => {
        await result.current.patch({ settings: { advanced_mode: true } })
      })

      expect(result.current.user).toEqual(POPULATED)
    })

    it('tracks pending across overlapping PATCHes', async () => {
      mockGet(POPULATED)
      const { result } = renderHook(() => useUser(), { wrapper })
      await waitFor(() => expect(result.current.user).toEqual(POPULATED))

      let resolveFirst!: (r: Response) => void
      let resolveSecond!: (r: Response) => void
      const firstResponse = new Promise<Response>((r) => (resolveFirst = r))
      const secondResponse = new Promise<Response>((r) => (resolveSecond = r))
      vi.mocked(fetch).mockReturnValueOnce(firstResponse).mockReturnValueOnce(secondResponse)

      let firstPromise!: Promise<void>
      let secondPromise!: Promise<void>
      act(() => {
        firstPromise = result.current.patch({ settings: { advanced_mode: true } })
      })
      await waitFor(() => expect(result.current.pending).toBe(true))

      act(() => {
        secondPromise = result.current.patch({
          settings: { stats_unlocked: true },
        })
      })

      // Both optimistic updates should have applied even before any PATCH resolves.
      expect(result.current.user?.settings.advanced_mode).toBe(true)
      expect(result.current.user?.settings.stats_unlocked).toBe(true)

      await act(async () => {
        resolveFirst({ ok: true, json: async () => POPULATED } as Response)
        await firstPromise
      })
      // Still pending due to second.
      expect(result.current.pending).toBe(true)

      await act(async () => {
        resolveSecond({ ok: true, json: async () => POPULATED } as Response)
        await secondPromise
      })
      await waitFor(() => expect(result.current.pending).toBe(false))

      // Both optimistic updates persisted (no clobber from server response).
      expect(result.current.user?.settings.advanced_mode).toBe(true)
      expect(result.current.user?.settings.stats_unlocked).toBe(true)
    })
  })
})
