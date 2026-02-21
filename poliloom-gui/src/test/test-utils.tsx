import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { vi } from 'vitest'
import { UserPreferencesContext } from '@/contexts/UserPreferencesContext'
import { UserProgressContext } from '@/contexts/UserProgressContext'
import { EvaluationSessionContext } from '@/contexts/EvaluationSessionContext'

// Mock useAuthSession to avoid next-auth SessionProvider dependency
vi.mock('@/hooks/useAuthSession', () => ({
  useAuthSession: () => ({
    session: { accessToken: 'mock-token' },
    status: 'authenticated',
    isAuthenticated: true,
  }),
}))

// Mock Next.js router
export const mockRouterPush = vi.fn()
export const mockRouterPrefetch = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: mockRouterPrefetch,
  }),
}))

// Mock fetch for tests that need to verify API calls
export const mockFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true }),
})
global.fetch = mockFetch as unknown as typeof fetch

// Mock functions exported for test assertions
export const mockSubmitAndAdvance = vi.fn().mockReturnValue({ sessionComplete: false })
export const mockStartSession = vi.fn()
export const mockEndSession = vi.fn()

// Mock providers with static values - no useEffects, no async side effects
const MockUserProgressProvider = ({ children }: { children: React.ReactNode }) => (
  <UserProgressContext.Provider
    value={{
      hasCompletedBasicTutorial: true,
      hasCompletedAdvancedTutorial: true,
      statsUnlocked: true,
      completeBasicTutorial: vi.fn(),
      completeAdvancedTutorial: vi.fn(),
      unlockStats: vi.fn(),
    }}
  >
    {children}
  </UserProgressContext.Provider>
)

const MockUserPreferencesProvider = ({ children }: { children: React.ReactNode }) => (
  <UserPreferencesContext.Provider
    value={{
      filters: [],
      languages: [],
      countries: [],
      loadingLanguages: false,
      loadingCountries: false,
      initialized: true,
      updateFilters: vi.fn(),
      isAdvancedMode: false,
      setAdvancedMode: vi.fn(),
    }}
  >
    {children}
  </UserPreferencesContext.Provider>
)

const MockEvaluationSessionProvider = ({ children }: { children: React.ReactNode }) => (
  <EvaluationSessionContext.Provider
    value={{
      isSessionActive: true,
      completedCount: 0,
      sessionGoal: 5,
      startSession: mockStartSession,
      submitAndAdvance: mockSubmitAndAdvance,
      endSession: mockEndSession,
    }}
  >
    {children}
  </EvaluationSessionContext.Provider>
)

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockUserProgressProvider>
      <MockUserPreferencesProvider>
        <MockEvaluationSessionProvider>{children}</MockEvaluationSessionProvider>
      </MockUserPreferencesProvider>
    </MockUserProgressProvider>
  )
}

const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
