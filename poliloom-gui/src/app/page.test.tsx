import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act } from '@testing-library/react'
import { render } from '@/test/test-utils'
import Home from './page'
import { mockPolitician } from '@/test/mock-data'

// Mock fetch for API calls
global.fetch = vi.fn()

// Mock localStorage
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  },
  writable: true,
})

// Mock navigator.languages for browser language detection
Object.defineProperty(navigator, 'languages', {
  value: ['en-US'],
  writable: true,
})

Object.defineProperty(navigator, 'language', {
  value: 'en-US',
  writable: true,
})

vi.mock('@/components/Header', () => ({
  Header: () => <div>Header</div>,
}))

vi.mock('@/components/PoliticianEvaluation', () => ({
  PoliticianEvaluation: () => <div>PoliticianEvaluation Component</div>,
}))

const mockUseSession = vi.fn()
const mockSignIn = vi.fn()
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
  signIn: (...args: unknown[]) => mockSignIn(...args),
}))

describe('Home Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Mock fetch for PreferencesProvider API calls
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString()

      if (urlStr.includes('/api/languages')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response)
      }

      if (urlStr.includes('/api/countries')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response)
      }

      if (urlStr.includes('/api/preferences')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
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

  it('renders main title and description', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    await act(async () => {
      render(<Home />)
    })

    expect(screen.getByText('PoliLoom Data Evaluation')).toBeInTheDocument()
    expect(
      screen.getByText('Help evaluate politician data extracted from Wikipedia and other sources'),
    ).toBeInTheDocument()
  })

  it('shows loading state initially', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'loading',
    })

    await act(async () => {
      render(<Home />)
    })

    expect(screen.getByText('Loading authentication status...')).toBeInTheDocument()
  })

  it('shows sign in button when user is unauthenticated', async () => {
    mockUseSession.mockReturnValue({
      data: null,
      status: 'unauthenticated',
    })

    await act(async () => {
      render(<Home />)
    })

    expect(
      screen.getByText('Please sign in with your MediaWiki account to start evaluating data.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Sign in with MediaWiki')).toBeInTheDocument()
  })

  it('shows PoliticianEvaluation component when authenticated with data', async () => {
    mockUseSession.mockReturnValue({
      data: { accessToken: 'test-token' },
      status: 'authenticated',
    })

    // Override the default mock to return politician data
    vi.mocked(fetch).mockImplementation((url) => {
      const urlStr = url.toString()

      if (urlStr.includes('/api/politicians')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [mockPolitician],
        } as Response)
      }

      // Use default mock for other endpoints
      if (
        urlStr.includes('/api/languages') ||
        urlStr.includes('/api/countries') ||
        urlStr.includes('/api/preferences')
      ) {
        return Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          json: async () => [],
        } as Response)
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: async () => [],
      } as Response)
    })

    await act(async () => {
      render(<Home />)
    })

    // Wait for the async operations to complete
    await waitFor(() => {
      expect(screen.getByText('PoliticianEvaluation Component')).toBeInTheDocument()
    })

    expect(screen.getByText('Header')).toBeInTheDocument()
  })
})
