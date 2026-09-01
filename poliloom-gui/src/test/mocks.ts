import { vi, beforeEach } from 'vitest'
import type { UserSettings } from '@/types'

// --- Mock functions (exported for test assertions and overrides) ---

// next/navigation
export const mockRouterPush = vi.fn()
export const mockRouterReplace = vi.fn()
export const mockRouterPrefetch = vi.fn()
export const mockUseParams = vi.fn()
export const mockUsePathname = vi.fn()
export const mockUseSearchParams = vi.fn()

// Contexts
export const mockUseNextPoliticianContext = vi.fn()
export const mockUseSettings = vi.fn()
export const mockUseFilters = vi.fn()

export const mockSettingsPatch = vi.fn().mockResolvedValue(undefined)
export const mockSetLanguages = vi.fn()
export const mockSetCountries = vi.fn()

// Re-export the fetch mock created in test/setup.ts
export const mockFetch = vi.mocked(fetch)

// --- vi.mock calls ---

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
    replace: mockRouterReplace,
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

vi.mock('@/contexts/SettingsContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/SettingsContext')>()
  return {
    ...actual,
    useSettings: () => mockUseSettings(),
  }
})

vi.mock('@/contexts/FilterContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/FilterContext')>()
  return {
    ...actual,
    useFilters: () => mockUseFilters(),
  }
})

// --- Default return values ---

export const defaultNextPolitician = {
  nextHref: '/politician/Q12345',
  politicianReady: true,
  allCaughtUp: false,
  loading: false,
}

export const defaultSettings: UserSettings = {
  advanced_mode: false,
  basic_tutorial_completed: true,
  advanced_tutorial_completed: true,
  stats_unlocked: true,
}

export const defaultSettingsContext = {
  settings: defaultSettings,
  patch: mockSettingsPatch,
}

export const defaultFiltersContext = {
  languageQids: [] as string[],
  countryQids: [] as string[],
  setLanguages: mockSetLanguages,
  setCountries: mockSetCountries,
}

// --- Reset defaults before each test ---

beforeEach(() => {
  mockUseNextPoliticianContext.mockReturnValue(defaultNextPolitician)
  mockUseSettings.mockReturnValue(defaultSettingsContext)
  mockUseFilters.mockReturnValue(defaultFiltersContext)
  mockUseParams.mockReturnValue({})
  mockUsePathname.mockReturnValue('/')
  mockUseSearchParams.mockReturnValue(new URLSearchParams())
  mockSettingsPatch.mockClear()
  mockSetLanguages.mockClear()
  mockSetCountries.mockClear()
})
