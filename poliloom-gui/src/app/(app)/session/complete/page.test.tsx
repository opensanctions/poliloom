import { describe, it, expect } from 'vitest'
import { screen, render } from '@testing-library/react'
import '@/test/mocks'
import CompletePage from './page'

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
