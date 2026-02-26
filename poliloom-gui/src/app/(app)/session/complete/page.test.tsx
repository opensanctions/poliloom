import { describe, it, expect, vi } from 'vitest'
import { screen, render } from '@testing-library/react'
import '@/test/test-utils'
import CompletePage from './page'

vi.mock('@/contexts/NextPoliticianContext', () => ({
  useNextPoliticianContext: () => ({
    nextHref: '/politician/Q12345',
    nextQid: 'Q12345',
    loading: false,
    enrichmentMeta: null,
    languageFilters: [],
    countryFilters: [],
    advanceNext: vi.fn(),
  }),
}))

vi.mock('@/contexts/EvaluationSessionContext', () => ({
  useEvaluationSession: () => ({
    isSessionActive: false,
    completedCount: 0,
    sessionGoal: 5,
    startSession: vi.fn(),
    submitAndAdvance: vi.fn(),
    endSession: vi.fn(),
  }),
}))

describe('Complete Page', () => {
  it('shows session complete message with politician count', () => {
    render(<CompletePage />)

    expect(screen.getByText('Session Complete!')).toBeInTheDocument()
    expect(screen.getByText(/reviewed 5 politicians/)).toBeInTheDocument()
  })

  it('shows Return Home linking to home page', () => {
    render(<CompletePage />)

    const link = screen.getByRole('link', { name: 'Return Home' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/')
  })
})
