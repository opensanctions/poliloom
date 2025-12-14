import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '@/test/test-utils'
import UnlockedPage from './page'

const mockUnlockStats = vi.fn()
vi.mock('@/contexts/UserProgressContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/UserProgressContext')>()
  return {
    ...actual,
    useUserProgress: () => ({
      unlockStats: mockUnlockStats,
    }),
  }
})

describe('Unlocked Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows stats unlocked message', () => {
    render(<UnlockedPage />)

    expect(screen.getByText('Stats Unlocked!')).toBeInTheDocument()
    expect(screen.getByText(/you've completed your first session/i)).toBeInTheDocument()
  })

  it('unlocks stats on mount', () => {
    render(<UnlockedPage />)

    expect(mockUnlockStats).toHaveBeenCalled()
  })

  it('shows View Stats linking to stats page', () => {
    render(<UnlockedPage />)

    const link = screen.getByRole('link', { name: 'View Stats' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/stats')
  })

  it('shows Start Another Round linking to evaluate page', () => {
    render(<UnlockedPage />)

    const link = screen.getByRole('link', { name: 'Start Another Round' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/evaluate')
  })
})
