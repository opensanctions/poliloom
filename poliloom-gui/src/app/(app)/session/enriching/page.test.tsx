import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, render } from '@testing-library/react'
import { mockRouterPush, mockUseNextPoliticianContext, defaultNextPolitician } from '@/test/mocks'
import EnrichingPage from './page'

beforeEach(() => {
  mockUseNextPoliticianContext.mockReturnValue({
    ...defaultNextPolitician,
    nextHref: '/session/enriching',
    politicianReady: false,
  })
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
      politicianReady: true,
    })

    render(<EnrichingPage />)

    expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
  })
})

describe('Enriching Page - all caught up', () => {
  it('shows all caught up message when no enrichable politicians', () => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/',
      allCaughtUp: true,
    })

    render(<EnrichingPage />)

    expect(screen.getByText('All Caught Up!')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'Return Home' })
    expect(link).toHaveAttribute('href', '/')
  })
})
