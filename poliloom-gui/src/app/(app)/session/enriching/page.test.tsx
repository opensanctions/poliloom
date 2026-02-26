import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, render } from '@testing-library/react'
import { mockRouterPush } from '@/test/test-utils'
import EnrichingPage from './page'

const mockUseNextPoliticianContext = vi.fn()
vi.mock('@/contexts/NextPoliticianContext', () => ({
  useNextPoliticianContext: () => mockUseNextPoliticianContext(),
}))

const defaultNextPolitician = {
  nextHref: null,
  nextQid: null,
  loading: false,
  enrichmentMeta: { has_enrichable_politicians: true },
  languageFilters: [],
  countryFilters: [],
  advanceNext: vi.fn(),
}

beforeEach(() => {
  mockUseNextPoliticianContext.mockReturnValue(defaultNextPolitician)
  mockRouterPush.mockClear()
})

describe('Enriching Page', () => {
  it('shows gathering data message when waiting for enrichment', () => {
    render(<EnrichingPage />)

    expect(screen.getByText('Gathering Data...')).toBeInTheDocument()
    expect(screen.getByText(/Our AI is reading Wikipedia/)).toBeInTheDocument()
  })

  it('does not auto-navigate when no nextHref', () => {
    render(<EnrichingPage />)

    expect(mockRouterPush).not.toHaveBeenCalled()
  })
})

describe('Enriching Page - politician available', () => {
  it('auto-navigates when nextHref becomes available', () => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/politician/Q12345',
      nextQid: 'Q12345',
      enrichmentMeta: null,
    })

    render(<EnrichingPage />)

    expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
  })
})

describe('Enriching Page - all caught up', () => {
  it('shows all caught up message when no enrichable politicians', () => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      enrichmentMeta: { has_enrichable_politicians: false },
    })

    render(<EnrichingPage />)

    expect(screen.getByText('All Caught Up!')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'Return Home' })
    expect(link).toHaveAttribute('href', '/')
  })
})
