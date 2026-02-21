import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render, mockFetch } from '@/test/test-utils'
import UnlockedPage from './page'

describe('Unlocked Page', () => {
  beforeEach(() => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        wikidata_id: 'Q12345',
        meta: { has_enrichable_politicians: true, total_matching_filters: 5 },
      }),
    })
  })

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
