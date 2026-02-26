import { describe, it, expect, vi } from 'vitest'
import { screen, render } from '@testing-library/react'
import '@/test/test-utils'
import UnlockedPage from './page'

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

vi.mock('@/contexts/UserProgressContext', () => ({
  useUserProgress: () => ({
    statsUnlocked: true,
    unlockStats: vi.fn(),
  }),
}))

describe('Unlocked Page', () => {
  it('shows stats unlocked message', () => {
    render(<UnlockedPage />)

    expect(screen.getByText('Stats Unlocked!')).toBeInTheDocument()
    expect(screen.getByText(/you've completed your first session/i)).toBeInTheDocument()
  })

  it('shows View Stats linking to stats page', () => {
    render(<UnlockedPage />)

    const link = screen.getByRole('link', { name: 'View Stats' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/stats')
  })
})
