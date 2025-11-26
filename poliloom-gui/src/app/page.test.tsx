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

vi.mock('@/components/layout/Header', () => ({
  Header: () => <div>Header</div>,
}))

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

describe('Home Page (Filter Selection)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default tutorial state - not completed
    mockUseTutorial.mockReturnValue({
      hasCompletedTutorial: false,
      completeTutorial: vi.fn(),
      resetTutorial: vi.fn(),
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
      expect(screen.getByText('Customize Your Review Session')).toBeInTheDocument()
    })

    expect(
      screen.getByText(
        "Select the countries and languages you're interested in reviewing. Leave filters empty to review all available politicians.",
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

  it('shows Begin Review Session button when tutorial completed', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    mockUseTutorial.mockReturnValue({
      hasCompletedTutorial: true,
      completeTutorial: vi.fn(),
      resetTutorial: vi.fn(),
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Begin Review Session')).toBeInTheDocument()
    })
  })

  it('renders Header component', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    await act(async () => {
      render(<Home />)
    })

    expect(screen.getByText('Header')).toBeInTheDocument()
  })
})
