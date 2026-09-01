import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, render } from '@testing-library/react'
import {
  mockRouterPush,
  mockFetch,
  mockUseNextPoliticianContext,
  mockUseFilters,
  defaultNextPolitician,
} from '@/test/mocks'
import { PoliticianEvaluation } from './PoliticianEvaluation'
import type { SourceResponse, Politician } from '@/types'
import { PropertyType } from '@/types'

const testSource: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test',
  url_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const politician: Politician = {
  id: 'pol-1',
  name: 'Test Politician',
  wikidata_id: 'Q987654',
  sources: [testSource],
  properties: [
    {
      id: 'prop-1',
      type: PropertyType.P569,
      value: '+1970-01-01T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [
        {
          id: 'ref-1',
          source: testSource,
          supporting_quotes: ['born on January 1, 1970'],
        },
      ],
    },
    {
      id: 'pos-1',
      type: PropertyType.P39,
      entity_id: 'Q555',
      entity_name: 'Mayor of Test City',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-2',
          source: testSource,
          supporting_quotes: ['served as mayor from 2020 to 2024'],
        },
      ],
    },
    {
      id: 'birth-1',
      type: PropertyType.P19,
      entity_id: 'Q123',
      entity_name: 'Test City',
      statement_id: null,
      sources: [
        {
          id: 'ref-3',
          source: testSource,
          supporting_quotes: ['was born in Test City'],
        },
      ],
    },
  ],
}

const politicianWithConflicts: Politician = {
  id: 'pol-2',
  name: 'Conflicted Politician',
  wikidata_id: 'Q111222',
  sources: [testSource],
  properties: [
    {
      id: 'prop-c1',
      type: PropertyType.P569,
      value: '+1970-01-02T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [{ id: 'ref-c1', source: testSource, supporting_quotes: ['born January 2'] }],
    },
    {
      id: 'prop-c2',
      type: PropertyType.P27,
      entity_id: 'Q142',
      entity_name: 'France',
      statement_id: null,
      sources: [
        {
          id: 'ref-c2',
          source: testSource,
          supporting_quotes: ['French politician'],
        },
      ],
    },
    {
      id: 'pos-c1',
      type: PropertyType.P39,
      entity_id: 'Q555',
      entity_name: 'Mayor of Test City',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [{ id: 'ref-c3', source: testSource, supporting_quotes: ['served as mayor'] }],
    },
    {
      id: 'pos-c2',
      type: PropertyType.P39,
      entity_id: 'Q777',
      entity_name: 'Council Member',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2018-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-c4',
          source: testSource,
          supporting_quotes: ['council member since 2018'],
        },
      ],
    },
    {
      id: 'birth-c1',
      type: PropertyType.P19,
      entity_id: 'Q123',
      entity_name: 'Test City',
      statement_id: null,
      sources: [
        {
          id: 'ref-c5',
          source: testSource,
          supporting_quotes: ['born in Test City'],
        },
      ],
    },
    {
      id: 'birth-c2',
      type: PropertyType.P19,
      entity_id: 'Q999',
      entity_name: 'New City',
      statement_id: null,
      sources: [
        {
          id: 'ref-c6',
          source: testSource,
          supporting_quotes: ['born in New City'],
        },
      ],
    },
  ],
}

describe('PoliticianEvaluation', () => {
  beforeEach(() => {
    CSS.highlights.clear()
    mockFetch.mockImplementation((_url, options) => {
      if (options?.method === 'PATCH') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, message: 'OK', errors: [] }),
        } as Response)
      }
      // GET requests (e.g. refetchPolitician) return the politician data
      return Promise.resolve({
        ok: true,
        json: async () => politician,
      } as Response)
    })
  })

  it('renders politician name and wikidata id', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Test Politician')).toBeInTheDocument()
    expect(screen.getByText('(Q987654)')).toBeInTheDocument()
  })

  it('renders properties section with property details', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Properties')).toBeInTheDocument()
    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('January 1, 1970')).toBeInTheDocument()
    expect(screen.getByText('"born on January 1, 1970"')).toBeInTheDocument()
  })

  it('renders positions section with position details', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
  })

  it('renders birthplaces section with birthplace details', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Birthplaces')).toBeInTheDocument()
  })

  it('allows users to evaluate items by accepting or rejecting', () => {
    render(<PoliticianEvaluation politician={politician} />)

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    const rejectButton = screen.getAllByText('× Reject')[0]

    fireEvent.click(acceptButton)
    expect(acceptButton).toHaveAttribute('class', expect.stringContaining('bg-success'))

    fireEvent.click(rejectButton)
    expect(rejectButton).toHaveAttribute('class', expect.stringContaining('bg-danger'))
  })

  it('shows "Skip Politician" when no evaluations and "Submit Evaluations & Next" when evaluations exist', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Evaluations & Next')).not.toBeInTheDocument()

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    fireEvent.click(acceptButton)

    expect(screen.getByText('Submit Evaluations & Next')).toBeInTheDocument()
    expect(screen.queryByText('Skip Politician')).not.toBeInTheDocument()
  })

  it('submits evaluations via API and navigates to the next politician', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    fireEvent.click(acceptButtons[0])

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654',
        expect.objectContaining({
          method: 'PATCH',
        }),
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
    })
  })

  it('preserves language filters when refetching after submission', async () => {
    mockUseFilters.mockReturnValue({
      languageQids: ['Q1860', 'Q188'],
      countryQids: [],
      setLanguages: vi.fn(),
      setCountries: vi.fn(),
    })

    render(<PoliticianEvaluation politician={politician} />)
    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Evaluations & Next'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654?languages=Q1860&languages=Q188',
      )
    })
  })

  describe('property grouping', () => {
    it('groups properties correctly by type and entity', () => {
      render(<PoliticianEvaluation politician={politicianWithConflicts} />)

      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
      expect(screen.getByText(/Council Member/)).toBeInTheDocument()
      expect(screen.getByText('Birthplaces')).toBeInTheDocument()
      expect(screen.getByText('Citizenships')).toBeInTheDocument()
    })
  })

  describe('source handling', () => {
    it('provides source viewing for items with sources', () => {
      render(<PoliticianEvaluation politician={politicianWithConflicts} />)

      const viewingButtons = screen.getAllByText(/Viewing/)
      expect(viewingButtons.length).toBeGreaterThan(0)

      expect(screen.getByTitle('Source')).toBeInTheDocument()
    })
  })
})

describe('PoliticianEvaluation - no next politician', () => {
  beforeEach(() => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/session/enriching',
      politicianReady: false,
    })
    mockFetch.mockImplementation((_url, options) => {
      if (options?.method === 'PATCH') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, message: 'OK', errors: [] }),
        } as Response)
      }
      return Promise.resolve({
        ok: true,
        json: async () => politician,
      } as Response)
    })
  })

  it('navigates to /session/enriching on submit when no next politician available', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    fireEvent.click(acceptButtons[0])

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/session/enriching')
    })
  })

  it('skips displayed extracted properties before navigating when no next politician is available', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    fireEvent.click(screen.getByText('Skip Politician'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            items: [
              { action: 'skip', id: 'prop-1' },
              { action: 'skip', id: 'pos-1' },
              { action: 'skip', id: 'birth-1' },
            ],
          }),
        }),
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/session/enriching')
    })
  })
})
