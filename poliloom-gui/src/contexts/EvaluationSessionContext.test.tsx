import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { EvaluationSessionProvider, useEvaluationSession } from './EvaluationSessionContext'
import { mockPolitician } from '@/test/mock-data'
import { Politician } from '@/types'

// Mock useAuthSession
vi.mock('@/hooks/useAuthSession', () => ({
  useAuthSession: () => ({
    session: { accessToken: 'mock-token' },
    status: 'authenticated',
    isAuthenticated: true,
  }),
}))

// Mock UserPreferencesContext with STABLE references to avoid infinite loops
// The context has a useEffect that clears politicians when filters change,
// and useMemo depends on filters - so a new array each render causes loops
const stableFilters: never[] = []
vi.mock('./UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    filters: stableFilters,
    initialized: true,
  }),
}))

// Create a second mock politician for testing advancement
const mockPolitician2: Politician = {
  ...mockPolitician,
  id: 'pol-2',
  name: 'Second Politician',
  wikidata_id: 'Q123456',
}

describe('EvaluationSessionContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Setup mock fetch - always returns same politicians (stable response)
    // has_enrichable_politicians: false prevents auto-polling
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/evaluations/politicians')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            politicians: [mockPolitician, mockPolitician2],
            meta: { has_enrichable_politicians: false, total_matching_filters: 10 },
          }),
        })
      }
      if (url.includes('/api/evaluations')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, message: 'OK', errors: [] }),
        })
      }
      return Promise.resolve({ ok: false })
    }) as unknown as typeof fetch
  })

  it('advances to next politician when session is reset', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <EvaluationSessionProvider>{children}</EvaluationSessionProvider>
    )

    const { result } = renderHook(() => useEvaluationSession(), { wrapper })

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.currentPolitician).not.toBeNull()
    })

    // Verify we start with first politician and have next pre-fetched
    expect(result.current.currentPolitician?.id).toBe('pol-1')
    expect(result.current.nextPolitician?.id).toBe('pol-2')
    expect(result.current.completedCount).toBe(0)

    // Reset the session (simulating "Start new round" on unmount)
    act(() => {
      result.current.resetSession()
    })

    // After reset, next politician should be promoted to current
    expect(result.current.currentPolitician?.id).toBe('pol-2')
    expect(result.current.completedCount).toBe(0)
  })
})
