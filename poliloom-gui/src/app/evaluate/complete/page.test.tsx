import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '@/test/test-utils'
import CompletePage from './page'

const mockResetSession = vi.fn()
const mockUseEvaluationSession = vi.fn()
vi.mock('@/contexts/EvaluationSessionContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/EvaluationSessionContext')>()
  return {
    ...actual,
    useEvaluationSession: () => mockUseEvaluationSession(),
  }
})

describe('Complete Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockUseEvaluationSession.mockReturnValue({
      sessionGoal: 5,
      resetSession: mockResetSession,
    })
  })

  it('shows session complete message with politician count', () => {
    render(<CompletePage />)

    expect(screen.getByText('Session Complete!')).toBeInTheDocument()
    expect(screen.getByText(/reviewed 5 politicians/)).toBeInTheDocument()
  })

  it('resets session on mount', () => {
    render(<CompletePage />)

    expect(mockResetSession).toHaveBeenCalled()
  })

  it('shows Start Another Round linking to evaluate page', () => {
    render(<CompletePage />)

    const link = screen.getByRole('link', { name: 'Start Another Round' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/evaluate')
  })

  it('shows Return Home linking to home page', () => {
    render(<CompletePage />)

    const link = screen.getByRole('link', { name: 'Return Home' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/')
  })
})
