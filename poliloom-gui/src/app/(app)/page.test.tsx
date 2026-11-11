import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, act, render, fireEvent } from '@testing-library/react'
import {
  mockUseSettings,
  mockRouterPush,
  mockRouterReplace,
  mockFetch,
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
  mockUseSession.mockReturnValue({ data: null, status: 'loading' })
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => ({ wikidata_id: 'Q12345' }),
  } as Response)
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
  beforeEach(() => {
    mockUseSettings.mockReturnValue(defaultSettingsContext)
  })

  it('claims a politician only when starting a session and navigates to its QID', async () => {
    mockUseFilters.mockReturnValue({
      ...defaultFiltersContext,
      languageQids: ['Q1860'],
      countryQids: ['Q30'],
    })
    render(<HomeContent languages={[]} countries={[]} />)

    expect(mockFetch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Start Your Session' }))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1)
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/claim?languages=Q1860&countries=Q30',
        { method: 'POST' },
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
    })
  })

  it('shows the disabled empty state after a null claim', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ wikidata_id: null }),
    } as Response)
    render(<HomeContent languages={[]} countries={[]} />)

    fireEvent.click(screen.getByRole('button', { name: 'Start Your Session' }))

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/?empty=1')
      expect(screen.getByText(/No politicians found for your current filters/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Start Your Session' })).toBeDisabled()
    })
  })

  it('renders the empty state when returning home after a null claim', () => {
    render(<HomeContent languages={[]} countries={[]} initialEmptyResult />)

    expect(screen.getByText(/No politicians found for your current filters/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start Your Session' })).toBeDisabled()
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('re-enables Start Session when filters change after an empty result', () => {
    render(
      <HomeContent
        languages={[language({ sources_count: 10 })]}
        countries={[]}
        initialEmptyResult
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /English/ }))

    expect(mockSetLanguages).toHaveBeenCalledWith(['Q1860'])
    expect(mockRouterReplace).toHaveBeenCalledWith('/')
    expect(screen.getByRole('button', { name: 'Start Your Session' })).not.toBeDisabled()
    expect(mockFetch).not.toHaveBeenCalled()
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
