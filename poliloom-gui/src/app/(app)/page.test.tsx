import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act, render } from '@testing-library/react'
import {
  mockUseNextPoliticianContext,
  mockUseSettings,
  defaultNextPolitician,
  defaultSettingsContext,
  defaultSettings,
} from '@/test/mocks'
import { HomeContent } from './HomeContent'

const mockUseSession = vi.fn()
const mockSignIn = vi.fn()
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
  signIn: (...args: unknown[]) => mockSignIn(...args),
}))

beforeEach(() => {
  mockUseNextPoliticianContext.mockReturnValue({
    ...defaultNextPolitician,
    nextHref: '/',
    politicianReady: false,
  })
  mockUseSession.mockReturnValue({ data: null, status: 'loading' })
  mockUseSettings.mockReturnValue({
    ...defaultSettingsContext,
    settings: {
      ...defaultSettings,
      basic_tutorial_completed: false,
      advanced_tutorial_completed: false,
      stats_unlocked: false,
    },
  })
})

describe('Home Page - waiting for enrichment', () => {
  it('CTA links to /session/enriching when waiting for enrichment', async () => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/session/enriching',
    })
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: {
        ...defaultSettings,
        advanced_tutorial_completed: false,
        stats_unlocked: false,
      },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
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
      render(<HomeContent languages={[]} countries={[]} />)
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
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Evaluation Session button when basic tutorial completed in basic mode', async () => {
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: {
        ...defaultSettings,
        advanced_tutorial_completed: false,
        stats_unlocked: false,
      },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Your Session')).toBeInTheDocument()
    })
  })

  it('shows Start Advanced Tutorial button when basic completed but advanced not completed in advanced mode', async () => {
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: {
        ...defaultSettings,
        advanced_mode: true,
        advanced_tutorial_completed: false,
        stats_unlocked: false,
      },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Advanced Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Evaluation Session button when both tutorials completed in advanced mode', async () => {
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: { ...defaultSettings, advanced_mode: true },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Your Session')).toBeInTheDocument()
    })
  })

  it('shows Start Tutorial button when no tutorials completed in advanced mode', async () => {
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: {
        ...defaultSettings,
        advanced_mode: true,
        basic_tutorial_completed: false,
        advanced_tutorial_completed: false,
        stats_unlocked: false,
      },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Tutorial')).toBeInTheDocument()
    })
  })
})
