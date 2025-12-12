import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { render } from '@/test/test-utils'
import CompletePage from './page'

const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

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

  it('shows Start Another Round as primary action', () => {
    render(<CompletePage />)

    expect(screen.getByRole('button', { name: 'Start Another Round' })).toBeInTheDocument()
  })

  it('shows Return Home as secondary action', () => {
    render(<CompletePage />)

    expect(screen.getByRole('button', { name: 'Return Home' })).toBeInTheDocument()
  })

  it('navigates to evaluate page when clicking Start Another Round', () => {
    render(<CompletePage />)

    fireEvent.click(screen.getByRole('button', { name: 'Start Another Round' }))

    expect(mockResetSession).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/evaluate')
  })

  it('navigates to home page when clicking Return Home', () => {
    render(<CompletePage />)

    fireEvent.click(screen.getByRole('button', { name: 'Return Home' }))

    expect(mockResetSession).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/')
  })
})
