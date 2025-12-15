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
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    back: vi.fn(),
  }),
}))

// Mock fetch for tests that need to verify API calls
export const mockFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true }),
})
global.fetch = mockFetch as unknown as typeof fetch

// Mock functions exported for test assertions
export const mockSubmitEvaluation = vi.fn().mockResolvedValue({ sessionComplete: false })
export const mockSkipPolitician = vi.fn()

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
      setTheme: vi.fn(),
    }}
  >
    {children}
  </UserPreferencesContext.Provider>
)

const MockEvaluationSessionProvider = ({ children }: { children: React.ReactNode }) => (
  <EvaluationSessionContext.Provider
    value={{
      currentPolitician: null,
      nextPolitician: null,
      loading: false,
      completedCount: 0,
      sessionGoal: 5,
      isSessionComplete: false,
      submitEvaluation: mockSubmitEvaluation,
      skipPolitician: mockSkipPolitician,
      resetSession: vi.fn(),
      loadPoliticians: vi.fn(),
      enrichmentMeta: null,
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
