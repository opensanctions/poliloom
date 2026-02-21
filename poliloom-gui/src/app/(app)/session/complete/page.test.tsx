import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render, mockFetch } from '@/test/test-utils'
import CompletePage from './page'

describe('Complete Page', () => {
  beforeEach(() => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        wikidata_id: 'Q12345',
        meta: { has_enrichable_politicians: true, total_matching_filters: 5 },
      }),
    })
  })

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
