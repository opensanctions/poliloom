import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { render } from '@/test/test-utils'
import UnlockedPage from './page'

const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

const mockResetSession = vi.fn()
vi.mock('@/contexts/EvaluationSessionContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/EvaluationSessionContext')>()
  return {
    ...actual,
    useEvaluationSession: () => ({
      resetSession: mockResetSession,
    }),
  }
})

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
    expect(
      screen.getByText(/completed your first session and unlocked the community stats page/),
    ).toBeInTheDocument()
  })

  it('calls unlockStats on mount', () => {
    render(<UnlockedPage />)

    expect(mockUnlockStats).toHaveBeenCalled()
  })

  it('shows View Stats as primary action', () => {
    render(<UnlockedPage />)

    expect(screen.getByRole('button', { name: 'View Stats' })).toBeInTheDocument()
  })

  it('shows Start Another Round as secondary action', () => {
    render(<UnlockedPage />)

    expect(screen.getByRole('button', { name: 'Start Another Round' })).toBeInTheDocument()
  })

  it('navigates to stats page when clicking View Stats', () => {
    render(<UnlockedPage />)

    fireEvent.click(screen.getByRole('button', { name: 'View Stats' }))

    expect(mockResetSession).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/stats')
  })

  it('navigates to evaluate page when clicking Start Another Round', () => {
    render(<UnlockedPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Start Another Round' }))

    expect(mockResetSession).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/evaluate')
  })
})
