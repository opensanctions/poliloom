import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act, render, fireEvent } from '@testing-library/react'
import {
  mockUseNextPoliticianContext,
  mockUseSettings,
  defaultNextPolitician,
  defaultSettingsContext,
  defaultSettings,
  defaultFiltersContext,
  mockSetLanguages,
  mockUseFilters,
  mockUseLabelLanguages,
} from '@/test/mocks'
import { HomeContent } from './HomeContent'
import { country, language, labelTerms } from '@/test/factories'

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
    },
  })
})

describe('Home Page - review navigation', () => {
  it('CTA links directly to the next politician', async () => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/politician/Q12345',
    })
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: {
        ...defaultSettings,
        advanced_tutorial_completed: false,
      },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      const ctaButton = screen.getByRole('link', { name: 'Start Your Session' })
      expect(ctaButton).toHaveAttribute('href', '/politician/Q12345')
    })
  })
})

describe('Home Page (Filter Selection)', () => {
  it('prevents removing the last selected language', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q1860'],
    })

    render(<HomeContent languages={[language({ sources_count: 10 })]} countries={[]} />)

    const english = screen.getByRole('button', { name: /English/ })
    expect(english).toBeDisabled()
    fireEvent.click(english)
    expect(mockSetLanguages).not.toHaveBeenCalled()
  })

  it('renders filter options in the browser language', () => {
    mockUseLabelLanguages.mockReturnValue(['sv'])

    render(
      <HomeContent
        languages={[
          language({ sources_count: 10, terms: labelTerms({ en: 'English', sv: 'Engelska' }) }),
        ]}
        countries={[
          country({
            citizenships_count: 10,
            terms: labelTerms({ en: 'United States', sv: 'USA' }),
          }),
        ]}
      />,
    )

    expect(screen.getByRole('button', { name: /Engelska/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /USA/ })).toBeInTheDocument()
  })

  it('renders home page with filter options', async () => {
    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Configure Your Session')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Pick your focus, then work through politicians at your own pace.'),
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

  it('shows Begin Review Session button when basic tutorial completed in basic mode', async () => {
    mockUseSettings.mockReturnValue({
      ...defaultSettingsContext,
      settings: {
        ...defaultSettings,
        advanced_tutorial_completed: false,
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
      },
    })

    await act(async () => {
      render(<HomeContent languages={[]} countries={[]} />)
    })

    await waitFor(() => {
      expect(screen.getByText('Start Advanced Tutorial')).toBeInTheDocument()
    })
  })

  it('shows Begin Review Session button when both tutorials completed in advanced mode', async () => {
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
