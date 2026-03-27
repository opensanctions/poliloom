import { describe, it, expect } from 'vitest'
import { screen, render } from '@testing-library/react'
import '@/test/mocks'
import UnlockedPage from './page'

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
