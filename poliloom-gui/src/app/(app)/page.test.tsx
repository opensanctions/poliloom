import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act, render } from '@testing-library/react'
import {
  mockUseNextPoliticianContext,
  mockUseUserProgress,
  mockUseUserPreferences,
  defaultNextPolitician,
  defaultUserProgress,
  defaultUserPreferences,
} from '@/test/mocks'
import Home from './page'

const mockUseSession = vi.fn()
const mockSignIn = vi.fn()
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
  signIn: (...args: unknown[]) => mockSignIn(...args),
}))

// Mock navigator.languages for browser language detection
Object.defineProperty(navigator, 'languages', {
  value: ['en-US'],
  writable: true,
})

Object.defineProperty(navigator, 'language', {
  value: 'en-US',
  writable: true,
})

beforeEach(() => {
  mockUseNextPoliticianContext.mockReturnValue({
    ...defaultNextPolitician,
    nextHref: '/',
    politicianReady: false,
  })
  mockUseSession.mockReturnValue({ data: null, status: 'loading' })
  mockUseUserProgress.mockReturnValue({
    ...defaultUserProgress,
    hasCompletedBasicTutorial: false,
    hasCompletedAdvancedTutorial: false,
    statsUnlocked: false,
  })

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

describe('Home Page - waiting for enrichment', () => {
  it('CTA links to /session/enriching when waiting for enrichment', async () => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/session/enriching',
    })
    mockUseUserProgress.mockReturnValue({
      ...defaultUserProgress,
      hasCompletedAdvancedTutorial: false,
      statsUnlocked: false,
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      const ctaButton = screen.getByRole('link', { name: 'Start Your Session' })
      expect(ctaButton).toHaveAttribute('href', '/session/enriching')
    })
  })
})

describe('Home Page (Filter Selection)', () => {
  it('renders home page with filter options', async () => {
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
    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Evaluation Session button when basic tutorial completed in basic mode', async () => {
    mockUseUserProgress.mockReturnValue({
      ...defaultUserProgress,
      hasCompletedAdvancedTutorial: false,
      statsUnlocked: false,
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Your Session')).toBeInTheDocument()
    })
  })

  it('shows Start Advanced Tutorial button when basic completed but advanced not completed in advanced mode', async () => {
    mockUseUserProgress.mockReturnValue({
      ...defaultUserProgress,
      hasCompletedAdvancedTutorial: false,
      statsUnlocked: false,
    })
    mockUseUserPreferences.mockReturnValue({
      ...defaultUserPreferences,
      isAdvancedMode: true,
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Advanced Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Evaluation Session button when both tutorials completed in advanced mode', async () => {
    mockUseUserProgress.mockReturnValue(defaultUserProgress)
    mockUseUserPreferences.mockReturnValue({
      ...defaultUserPreferences,
      isAdvancedMode: true,
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Your Session')).toBeInTheDocument()
    })
  })

  it('shows Start Tutorial button when no tutorials completed in advanced mode', async () => {
    mockUseUserProgress.mockReturnValue({
      ...defaultUserProgress,
      hasCompletedBasicTutorial: false,
      hasCompletedAdvancedTutorial: false,
      statsUnlocked: false,
    })
    mockUseUserPreferences.mockReturnValue({
      ...defaultUserPreferences,
      isAdvancedMode: true,
    })

    await act(async () => {
      render(<Home />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Tutorial')).toBeInTheDocument()
    })
  })
})
