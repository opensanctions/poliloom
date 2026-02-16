import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '@/test/test-utils'
import CompletePage from './page'

vi.mock('@/contexts/EvaluationSessionContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/EvaluationSessionContext')>()
  return {
    ...actual,
    useEvaluationSession: () => ({
      sessionGoal: 5,
    }),
  }
})

describe('Complete Page', () => {
  it('shows session complete message with politician count', () => {
    render(<CompletePage />)

    expect(screen.getByText('Session Complete!')).toBeInTheDocument()
    expect(screen.getByText(/reviewed 5 politicians/)).toBeInTheDocument()
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
