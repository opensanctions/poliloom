import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, act } from '@testing-library/react'
import { render } from '@/test/test-utils'
import EvaluatePage from './page'
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

const mockUsePoliticians = vi.fn()
vi.mock('@/contexts/PoliticiansContext', () => ({
  usePoliticians: () => mockUsePoliticians(),
  PoliticiansProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('Evaluate Page', () => {
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

  it('shows loading state when loading politicians', async () => {
    mockUsePoliticians.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: true,
      refetch: vi.fn(),
      loadPoliticians: vi.fn(),
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(screen.getByText('Loading politician data...')).toBeInTheDocument()
    expect(screen.getByText('Header')).toBeInTheDocument()
  })

  it('shows no politicians message when not loading and no politician available', async () => {
    const mockLoadPoliticians = vi.fn()
    mockUsePoliticians.mockReturnValue({
      currentPolitician: null,
      nextPolitician: null,
      loading: false,
      refetch: vi.fn(),
      loadPoliticians: mockLoadPoliticians,
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(
      screen.getByText(/Currently no politicians available, we're enriching more/),
    ).toBeInTheDocument()
    expect(screen.getByText('preferences')).toBeInTheDocument()
    expect(screen.getByText('reload')).toBeInTheDocument()
  })

  it('shows PoliticianEvaluation component when politician data is available', async () => {
    const mockRefetch = vi.fn()
    mockUsePoliticians.mockReturnValue({
      currentPolitician: mockPolitician,
      nextPolitician: null,
      loading: false,
      refetch: mockRefetch,
      loadPoliticians: vi.fn(),
    })

    await act(async () => {
      render(<EvaluatePage />)
    })

    expect(screen.getByText('PoliticianEvaluation Component')).toBeInTheDocument()
    expect(screen.getByText('Header')).toBeInTheDocument()
  })
})
