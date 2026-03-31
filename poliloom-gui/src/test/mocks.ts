import { vi, beforeEach } from 'vitest'

// --- Mock functions (exported for test assertions and overrides) ---

// next/navigation
export const mockRouterPush = vi.fn()
export const mockRouterPrefetch = vi.fn()
export const mockUseParams = vi.fn()
export const mockUsePathname = vi.fn()
export const mockUseSearchParams = vi.fn()

// Contexts
export const mockUseNextPoliticianContext = vi.fn()
export const mockUseEvaluationSession = vi.fn()
export const mockUseUserProgress = vi.fn()
export const mockUseUserPreferences = vi.fn()

// Shared action mocks (used in defaultEvaluationSession)
export const mockSubmitAndAdvance = vi.fn()
export const mockStartSession = vi.fn()
export const mockEndSession = vi.fn()

// Re-export the fetch mock created in test/setup.ts
export const mockFetch = vi.mocked(fetch)

// --- vi.mock calls ---

vi.mock('@/hooks/useAuthSession', () => ({
  useAuthSession: () => ({
    session: { accessToken: 'mock-token' },
    status: 'authenticated',
    isAuthenticated: true,
  }),
}))

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    isIframeLoaded: true,
    handleIframeLoad: vi.fn(),
    highlightText: vi.fn(),
  }),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: mockRouterPrefetch,
  }),
  useParams: () => mockUseParams(),
  usePathname: () => mockUsePathname(),
  useSearchParams: () => mockUseSearchParams(),
}))

vi.mock('@/contexts/NextPoliticianContext', () => ({
  useNextPoliticianContext: () => mockUseNextPoliticianContext(),
}))

vi.mock('@/contexts/EvaluationSessionContext', () => ({
  useEvaluationSession: () => mockUseEvaluationSession(),
}))

vi.mock('@/contexts/UserProgressContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserProgressContext')>()
  return {
    ...actual,
    useUserProgress: () => mockUseUserProgress(),
  }
})

vi.mock('@/contexts/UserPreferencesContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserPreferencesContext')>()
  return {
    ...actual,
    useUserPreferences: () => mockUseUserPreferences(),
  }
})

// --- Default return values ---

export const defaultNextPolitician = {
  nextHref: '/politician/Q12345',
  politicianReady: true,
  allCaughtUp: false,
  loading: false,
  languageFilters: [],
  countryFilters: [],
}

export const defaultEvaluationSession = {
  isSessionActive: false,
  completedCount: 0,
  sessionGoal: 5,
  startSession: mockStartSession,
  submitAndAdvance: mockSubmitAndAdvance,
  endSession: mockEndSession,
}

export const defaultUserProgress = {
  hasCompletedBasicTutorial: true,
  hasCompletedAdvancedTutorial: true,
  statsUnlocked: true,
  completeBasicTutorial: vi.fn(),
  completeAdvancedTutorial: vi.fn(),
  unlockStats: vi.fn(),
}

export const defaultUserPreferences = {
  filters: [],
  languages: [],
  countries: [],
  loadingLanguages: false,
  loadingCountries: false,
  updateFilters: vi.fn(),
  isAdvancedMode: false,
  setAdvancedMode: vi.fn(),
}

// --- Reset defaults before each test ---

beforeEach(() => {
  mockUseNextPoliticianContext.mockReturnValue(defaultNextPolitician)
  mockUseEvaluationSession.mockReturnValue(defaultEvaluationSession)
  mockUseUserProgress.mockReturnValue(defaultUserProgress)
  mockUseUserPreferences.mockReturnValue(defaultUserPreferences)
  mockUseParams.mockReturnValue({})
  mockUsePathname.mockReturnValue('/')
  mockUseSearchParams.mockReturnValue(new URLSearchParams())
})
