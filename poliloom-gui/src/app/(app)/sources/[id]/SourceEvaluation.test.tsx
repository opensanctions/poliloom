import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@/test/highlight-mocks'
import { SourceEvaluation } from './SourceEvaluation'
import type { Politician } from '@/types'
import { PropertyType } from '@/types'

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'source-42' }),
}))

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

const politician: Politician = {
  id: 'pol-1',
  name: 'Test Politician',
  wikidata_id: 'Q100',
  sources: [
    {
      id: 'src-1',
      url: 'https://example.com',
      url_hash: 'abc',
      fetch_timestamp: '2024-01-01T00:00:00Z',
      status: 'done',
    },
  ],
  properties: [
    {
      id: 'prop-1',
      type: PropertyType.P569,
      value: '+1990-05-15T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [
        {
          id: 'ref-1',
          source: {
            id: 'src-1',
            url: 'https://example.com',
            url_hash: 'abc',
            fetch_timestamp: '2024-01-01T00:00:00Z',
            status: 'done' as const,
          },
          supporting_quotes: ['born May 15'],
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn()
})

describe('SourceEvaluation', () => {
  it('renders politicians via EvaluationView', () => {
    render(<SourceEvaluation politicians={[politician]} />)
    expect(screen.getByText('Test Politician')).toBeInTheDocument()
  })

  it('submits evaluations to correct source endpoint', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'ok', errors: [] }),
    })
    global.fetch = mockFetch

    render(<SourceEvaluation politicians={[politician]} />)

    // Accept the property
    const acceptButton = screen.getByRole('button', { name: /Accept/ })
    fireEvent.click(acceptButton)

    // Submit
    const submitButton = screen.getByRole('button', { name: /Submit/ })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/sources/source-42',
        expect.objectContaining({
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    // Verify the body contains the politician's actions
    const call = mockFetch.mock.calls[0]
    const body = JSON.parse(call[1].body)
    expect(body.items['pol-1']).toEqual([{ action: 'accept', id: 'prop-1' }])
  })

  it('disables submit button when no changes exist', () => {
    render(<SourceEvaluation politicians={[politician]} />)

    const submitButton = screen.getByRole('button', { name: /Submit/ })
    expect(submitButton).toBeDisabled()
  })
})
