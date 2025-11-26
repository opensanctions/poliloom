import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { vi } from 'vitest'
import { UserPreferencesContext } from '@/contexts/UserPreferencesContext'
import { TutorialContext } from '@/contexts/TutorialContext'
import { EvaluationSessionContext } from '@/contexts/EvaluationSessionContext'

// Mock useAuthSession to avoid next-auth SessionProvider dependency
vi.mock('@/hooks/useAuthSession', () => ({
  useAuthSession: () => ({
    session: { accessToken: 'mock-token' },
    status: 'authenticated',
    isAuthenticated: true,
  }),
}))

// Mock fetch for tests that need to verify API calls
export const mockFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true }),
})
global.fetch = mockFetch as unknown as typeof fetch

// Mock functions exported for test assertions
export const mockSubmitEvaluation = vi.fn()
export const mockSkipPolitician = vi.fn()

// Mock providers with static values - no useEffects, no async side effects
const MockTutorialProvider = ({ children }: { children: React.ReactNode }) => (
  <TutorialContext.Provider
    value={{
      hasCompletedTutorial: true,
      completeTutorial: vi.fn(),
      resetTutorial: vi.fn(),
    }}
  >
    {children}
  </TutorialContext.Provider>
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
    }}
  >
    {children}
  </EvaluationSessionContext.Provider>
)

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockTutorialProvider>
      <MockUserPreferencesProvider>
        <MockEvaluationSessionProvider>{children}</MockEvaluationSessionProvider>
      </MockUserPreferencesProvider>
    </MockTutorialProvider>
  )
}

const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
