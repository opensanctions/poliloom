import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act } from '@testing-library/react'
import { render } from '@/test/test-utils'
import Home from './page'

// Mock fetch for API calls
global.fetch = vi.fn()

// Mock navigator.languages for browser language detection
Object.defineProperty(navigator, 'languages', {
  value: ['en-US'],
  writable: true,
})

Object.defineProperty(navigator, 'language', {
  value: 'en-US',
  writable: true,
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}))

const mockUseSession = vi.fn()
const mockSignIn = vi.fn()
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
  signIn: (...args: unknown[]) => mockSignIn(...args),
}))

const mockUseTutorial = vi.fn()
vi.mock('@/contexts/TutorialContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/TutorialContext')>()
  return {
    ...actual,
    useTutorial: () => mockUseTutorial(),
  }
})

const mockUseUserPreferences = vi.fn()
vi.mock('@/contexts/UserPreferencesContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserPreferencesContext')>()
  return {
    ...actual,
    useUserPreferences: () => mockUseUserPreferences(),
  }
})

describe('Home Page (Filter Selection)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default tutorial state - not completed
    mockUseTutorial.mockReturnValue({
      hasCompletedBasicTutorial: false,
      hasCompletedAdvancedTutorial: false,
      completeBasicTutorial: vi.fn(),
      completeAdvancedTutorial: vi.fn(),
      resetTutorial: vi.fn(),
    })

    // Default user preferences - basic mode
    mockUseUserPreferences.mockReturnValue({
      filters: [],
      languages: [],
      countries: [],
      loadingLanguages: false,
      loadingCountries: false,
      initialized: true,
      updateFilters: vi.fn(),
      isAdvancedMode: false,
      setAdvancedMode: vi.fn(),
    })

    // Mock fetch for API calls
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString()

      if (urlStr.includes('/api/languages')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [
            { wikidata_id: 'Q1860', name: 'English' },
            { wikidata_id: 'Q188', name: 'German' },
          ],
        } as Response)
      }

      if (urlStr.includes('/api/countries')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [
            { wikidata_id: 'Q30', name: 'United States' },
            { wikidata_id: 'Q183', name: 'Germany' },
          ],
        } as Response)
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response)
    })
  })

  it('renders home page with filter options', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Configure Your Session')).toBeInTheDocument()
    })

    expect(
      screen.getByText(
        'Pick your focus, then work through a batch of politicians at your own pace.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('What languages can you read?')).toBeInTheDocument()
    expect(screen.getByText('Which countries are you interested in?')).toBeInTheDocument()
  })

  it('shows Start Tutorial button when tutorial not completed', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Evaluation Session button when basic tutorial completed in basic mode', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    mockUseTutorial.mockReturnValue({
      hasCompletedBasicTutorial: true,
      hasCompletedAdvancedTutorial: false,
      completeBasicTutorial: vi.fn(),
      completeAdvancedTutorial: vi.fn(),
      resetTutorial: vi.fn(),
    })

    // Basic mode (default from beforeEach)
    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Your Session')).toBeInTheDocument()
    })
  })

  it('shows Start Advanced Tutorial button when basic completed but advanced not completed in advanced mode', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    mockUseTutorial.mockReturnValue({
      hasCompletedBasicTutorial: true,
      hasCompletedAdvancedTutorial: false,
      completeBasicTutorial: vi.fn(),
      completeAdvancedTutorial: vi.fn(),
      resetTutorial: vi.fn(),
    })

    mockUseUserPreferences.mockReturnValue({
      filters: [],
      languages: [],
      countries: [],
      loadingLanguages: false,
      loadingCountries: false,
      initialized: true,
      updateFilters: vi.fn(),
      isAdvancedMode: true,
      setAdvancedMode: vi.fn(),
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Advanced Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Evaluation Session button when both tutorials completed in advanced mode', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    mockUseTutorial.mockReturnValue({
      hasCompletedBasicTutorial: true,
      hasCompletedAdvancedTutorial: true,
      completeBasicTutorial: vi.fn(),
      completeAdvancedTutorial: vi.fn(),
      resetTutorial: vi.fn(),
    })

    mockUseUserPreferences.mockReturnValue({
      filters: [],
      languages: [],
      countries: [],
      loadingLanguages: false,
      loadingCountries: false,
      initialized: true,
      updateFilters: vi.fn(),
      isAdvancedMode: true,
      setAdvancedMode: vi.fn(),
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Your Session')).toBeInTheDocument()
    })
  })

  it('shows Start Tutorial button when no tutorials completed in advanced mode', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    // No tutorials completed (default from beforeEach)
    mockUseUserPreferences.mockReturnValue({
      filters: [],
      languages: [],
      countries: [],
      loadingLanguages: false,
      loadingCountries: false,
      initialized: true,
      updateFilters: vi.fn(),
      isAdvancedMode: true,
      setAdvancedMode: vi.fn(),
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Tutorial')).toBeInTheDocument()
    })
  })
})
