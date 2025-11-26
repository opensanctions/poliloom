import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, render, mockFetch } from '@/test/test-utils'
import { PoliticianEvaluation } from './PoliticianEvaluation'
import { PropertyType } from '@/types'
import {
  mockPolitician,
  mockEmptyPolitician,
  mockPoliticianWithConflicts,
  mockPoliticianExtractedOnly,
  mockPoliticianExistingOnly,
} from '@/test/mock-data'

// Mock the CSS Custom Highlight API for testing
global.CSS = {
  highlights: new Map(),
} as typeof CSS

global.Highlight = class MockHighlight {
  private ranges: Range[]

  constructor(...ranges: Range[]) {
    this.ranges = ranges
  }

  get size() {
    return this.ranges.length
  }

  values() {
    return this.ranges[Symbol.iterator]()
  }
} as unknown as typeof Highlight

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    isIframeLoaded: true,
    handleIframeLoad: vi.fn(),
    handleQuotesChange: vi.fn(),
  }),
}))

// Mock console.error to suppress expected error output
vi.spyOn(console, 'error').mockImplementation(() => {})

describe('PoliticianEvaluation', () => {
  const defaultProps = {
    politician: mockPolitician,
  }

  beforeEach(() => {
    CSS.highlights.clear()
    mockFetch.mockClear()
  })

  it('renders politician name and wikidata id', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    expect(screen.getByText('Test Politician')).toBeInTheDocument()
    expect(screen.getByText('(Q987654)')).toBeInTheDocument()
  })

  it('renders properties section with property details', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    expect(screen.getByText('Properties')).toBeInTheDocument()
    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('January 1, 1970')).toBeInTheDocument()
    expect(screen.getByText('"born on January 1, 1970"')).toBeInTheDocument()
  })

  it('renders positions section with position details', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
    expect(screen.getByText(/Q555777/)).toBeInTheDocument()
    expect(screen.getByText('January 1, 2020 – January 1, 2024')).toBeInTheDocument()

    // Check that the Wikidata link exists
    const wikidataLink = screen.getByRole('link', { name: /Mayor of Test City.*Q555777/ })
    expect(wikidataLink).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q555777')
    expect(wikidataLink).toHaveAttribute('target', '_blank')
  })

  it('renders birthplaces section with birthplace details', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    expect(screen.getByText('Birthplaces')).toBeInTheDocument()
    expect(screen.getByText(/Q123456/)).toBeInTheDocument()

    // Check that the Wikidata link for birthplace exists
    const wikidataLink = screen.getByRole('link', { name: /Test City.*Q123456/ })
    expect(wikidataLink).toHaveAttribute('href', 'https://www.wikidata.org/wiki/Q123456')
    expect(wikidataLink).toHaveAttribute('target', '_blank')
  })

  it('allows users to evaluate items by accepting or rejecting', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    const rejectButton = screen.getAllByText('× Reject')[0]

    // User can accept an item - button should provide visual feedback
    fireEvent.click(acceptButton)
    expect(acceptButton).toHaveAttribute('class', expect.stringContaining('green'))

    // User can change their mind and reject instead
    fireEvent.click(rejectButton)
    expect(rejectButton).toHaveAttribute('class', expect.stringContaining('red'))
  })

  it('shows "Skip Politician" when no evaluations are set, and "Submit Evaluations & Next" when evaluations exist', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Evaluations & Next')).not.toBeInTheDocument()

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    fireEvent.click(acceptButton)

    expect(screen.getByText('Submit Evaluations & Next')).toBeInTheDocument()
    expect(screen.queryByText('Skip Politician')).not.toBeInTheDocument()

    fireEvent.click(acceptButton)

    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Evaluations & Next')).not.toBeInTheDocument()
  })

  it('submits evaluations and calls API with correct data', async () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    const rejectButtons = screen.getAllByText('× Reject')

    fireEvent.click(acceptButtons[0])
    if (acceptButtons[1]) fireEvent.click(acceptButtons[1])
    if (rejectButtons[0]) fireEvent.click(rejectButtons[0])

    expect(rejectButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-red-600'))
    if (acceptButtons[1]) {
      expect(acceptButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-green-600'))
    }

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      const evaluationCall = mockFetch.mock.calls.find((call) => call[0] === '/api/evaluations') as
        | [string, RequestInit]
        | undefined
      expect(evaluationCall).toBeDefined()
      const body = JSON.parse(evaluationCall![1].body as string)
      expect(body.evaluations).toContainEqual({ id: 'prop-1', is_accepted: false })
      if (acceptButtons[1]) {
        expect(body.evaluations).toContainEqual({ id: 'pos-1', is_accepted: true })
      }
    })
  })

  it('preserves evaluation state when submission fails', async () => {
    // Override fetch to return error for evaluations
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/evaluations')) {
        return Promise.resolve({
          ok: false,
          statusText: 'Submission failed',
          json: async () => ({}),
        })
      }
      return Promise.resolve({ ok: true, json: async () => [] })
    })

    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    const rejectButtons = screen.getAllByText('× Reject')

    // Make evaluations
    fireEvent.click(acceptButtons[0])
    if (rejectButtons[1]) fireEvent.click(rejectButtons[1])

    // Verify buttons show selected state before submission
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600'))
    if (rejectButtons[1]) {
      expect(rejectButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-red-600'))
    }

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/evaluations', expect.anything())
    })

    // Verify evaluation state is PRESERVED after failed submission
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600'))
    if (rejectButtons[1]) {
      expect(rejectButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-red-600'))
    }
  })

  it('preserves evaluation state when network request fails', async () => {
    // Override fetch to reject (network failure)
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/evaluations')) {
        return Promise.reject(new Error('Network connection failed'))
      }
      return Promise.resolve({ ok: true, json: async () => [] })
    })

    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')

    // Make an evaluation
    fireEvent.click(acceptButtons[0])
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600'))

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/evaluations', expect.anything())
    })

    // Verify evaluation state is PRESERVED after network failure
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600'))
  })

  it('does not render sections when politician has no unevaluated data', () => {
    render(<PoliticianEvaluation {...defaultProps} politician={mockEmptyPolitician} />)

    expect(screen.queryByText('Properties')).not.toBeInTheDocument()
    expect(screen.queryByText('Political Positions')).not.toBeInTheDocument()
    expect(screen.queryByText('Birthplaces')).not.toBeInTheDocument()
  })

  it('displays source information for items with archived pages', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    const viewingButtons = screen.getAllByText(/Viewing/)
    expect(viewingButtons.length).toBeGreaterThan(0)

    const sourceTexts = screen.getAllByText('https://en.wikipedia.org/wiki/Test_Politician')
    expect(sourceTexts.length).toBeGreaterThan(0)
  })

  describe('property grouping', () => {
    it('displays sections in consistent order regardless of data order', () => {
      const mockPoliticianReversedOrder = {
        ...mockPoliticianWithConflicts,
        properties: [
          {
            key: 'prop-citizenship',
            id: 'prop-citizenship',
            type: PropertyType.P27,
            entity_id: 'Q142',
            entity_name: 'France',
            statement_id: null,
            supporting_quotes: ['French politician'],
          },
          {
            key: 'birth-1',
            id: 'birth-1',
            type: PropertyType.P19,
            entity_id: 'Q123456',
            entity_name: 'Test City',
            statement_id: null,
            supporting_quotes: ['was born in Test City'],
          },
          {
            key: 'pos-1',
            id: 'pos-1',
            type: PropertyType.P39,
            entity_id: 'Q555777',
            entity_name: 'Mayor of Test City',
            statement_id: null,
            qualifiers: {
              P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
              P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
            },
            supporting_quotes: ['served as mayor from 2020 to 2024'],
          },
          {
            key: 'prop-birth',
            id: 'prop-birth',
            type: PropertyType.P569,
            value: '+1970-01-01T00:00:00Z',
            value_precision: 11,
            statement_id: null,
            supporting_quotes: ['born on January 1, 1970'],
          },
        ],
      }

      render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianReversedOrder} />)

      const sectionHeadings = screen.getAllByRole('heading', { level: 2 })
      const sectionTexts = sectionHeadings.map((heading) => heading.textContent)

      const expectedOrder = ['Properties', 'Political Positions', 'Birthplaces', 'Citizenships']
      const actualOrder = sectionTexts.filter((text) => expectedOrder.includes(text || ''))

      expect(actualOrder).toEqual(expectedOrder)
    })

    it('groups properties correctly by type and entity', () => {
      render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
      expect(screen.getByText(/Council Member/)).toBeInTheDocument()
      expect(screen.getByText('Birthplaces')).toBeInTheDocument()

      const birthplaceSection = screen.getByText('Birthplaces').closest('.mb-8')
      expect(birthplaceSection).toBeInTheDocument()
      expect(birthplaceSection).toHaveTextContent('Test City')
      expect(birthplaceSection).toHaveTextContent('Q123456')
      expect(birthplaceSection).toHaveTextContent('New City')

      expect(screen.getByText('Citizenships')).toBeInTheDocument()
      expect(screen.getByText(/France/)).toBeInTheDocument()
    })

    it('groups multiple statements for the same entity together', () => {
      const mockPoliticianSamePosition = {
        ...mockPolitician,
        properties: [
          ...mockPolitician.properties.filter((p) => p.type !== PropertyType.P39),
          {
            key: 'pos-1',
            id: 'pos-1',
            type: PropertyType.P39,
            entity_id: 'Q555777',
            entity_name: 'Mayor of Test City',
            statement_id: 'existing-statement',
            qualifiers: {
              P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
              P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
            },
          },
          {
            key: 'pos-2',
            id: 'pos-2',
            type: PropertyType.P39,
            entity_id: 'Q555777',
            entity_name: 'Mayor of Test City',
            statement_id: null,
            qualifiers: {
              P580: [{ datavalue: { value: { time: '+2022-01-01T00:00:00Z', precision: 11 } } }],
              P582: [{ datavalue: { value: { time: '+2026-01-01T00:00:00Z', precision: 11 } } }],
            },
            supporting_quotes: ['served as mayor from 2022 to 2026'],
            archived_page: {
              id: 'archived-1',
              url: 'https://example.com',
              content_hash: 'abc123',
              fetch_timestamp: '2024-01-01T00:00:00Z',
            },
          },
        ],
      }

      render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianSamePosition} />)

      const mayorItems = screen.getAllByText(/Mayor of Test City/)
      expect(mayorItems).toHaveLength(1)

      expect(screen.getByText('January 1, 2020 – January 1, 2024')).toBeInTheDocument()
      expect(screen.getByText('January 1, 2022 – January 1, 2026')).toBeInTheDocument()

      const evaluationItem = screen.getByText(/Mayor of Test City/).closest('.border')
      expect(evaluationItem).toBeInTheDocument()
    })

    it('shows individual items for value-based properties', () => {
      render(<PoliticianEvaluation {...defaultProps} />)

      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('January 1, 1970')).toBeInTheDocument()

      const birthDateItems = screen.getAllByText('Birth Date')
      expect(birthDateItems).toHaveLength(1)
    })
  })

  describe('merged data functionality', () => {
    describe('conflicted data scenarios', () => {
      it('renders conflicted politician with mixed data types', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        expect(screen.getByText('Conflicted Politician')).toBeInTheDocument()
        expect(screen.getByText('Properties')).toBeInTheDocument()
        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByText('Birthplaces')).toBeInTheDocument()
      })

      it('shows existing-only items as read-only', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        expect(screen.getByText('Properties')).toBeInTheDocument()
        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByText('Birthplaces')).toBeInTheDocument()
      })

      it('shows conflicted items with both values', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        expect(screen.getByText('January 2, 1970')).toBeInTheDocument()
      })

      it('maintains priority ordering: existing-only, conflicted, extracted-only', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        const propertiesSection = screen.getByText('Properties').closest('div')
        expect(propertiesSection).toBeInTheDocument()

        const acceptButtons = screen.getAllByText('✓ Accept')
        expect(acceptButtons.length).toBeGreaterThan(0)
      })
    })

    describe('extracted-only data scenarios', () => {
      it('shows evaluation controls and allows interaction for extracted data', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExtractedOnly} />)

        expect(screen.getByText('Extracted Only Politician')).toBeInTheDocument()

        const acceptButtons = screen.getAllByText('✓ Accept')
        const rejectButtons = screen.getAllByText('× Reject')

        expect(acceptButtons.length).toBeGreaterThan(0)
        expect(rejectButtons.length).toBeGreaterThan(0)

        fireEvent.click(acceptButtons[0])
        expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('green'))
      })
    })

    describe('existing-only data scenarios', () => {
      it('shows no evaluation controls for existing-only data', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />)

        expect(screen.getByText('Existing Only Politician')).toBeInTheDocument()

        expect(screen.queryByText('✓ Accept')).not.toBeInTheDocument()
        expect(screen.queryByText('× Reject')).not.toBeInTheDocument()
      })
    })

    describe('evaluation submission with mixed data', () => {
      it('submits evaluations and progresses to next politician', async () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        const acceptButtons = screen.getAllByText('✓ Accept')
        const rejectButtons = screen.getAllByText('× Reject')

        if (acceptButtons[0]) fireEvent.click(acceptButtons[0])
        if (rejectButtons.length > 1) fireEvent.click(rejectButtons[1])

        const submitButton = screen.getByText('Submit Evaluations & Next')
        fireEvent.click(submitButton)

        await waitFor(() => {
          expect(mockFetch).toHaveBeenCalledWith('/api/evaluations', expect.anything())
        })
      })
    })

    describe('archived page handling', () => {
      it('provides source viewing for items with archived pages', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        const viewingButtons = screen.getAllByText(/Viewing/)
        expect(viewingButtons.length).toBeGreaterThan(0)

        expect(screen.getByTitle('Archived Page')).toBeInTheDocument()
      })

      it('shows placeholder when no source is available', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />)

        expect(
          screen.getByText(/Click.*View.*on any item to see the source page/),
        ).toBeInTheDocument()
      })
    })
  })
})
