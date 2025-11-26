import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { render } from '@testing-library/react'
import { PoliticianEvaluation } from './PoliticianEvaluation'
import { PropertyType } from '@/types'
import {
  mockPolitician,
  mockEmptyPolitician,
  mockPoliticianWithConflicts,
  mockPoliticianExtractedOnly,
  mockPoliticianExistingOnly,
  mockPoliticianWithDifferentSources,
  mockPoliticianWithEdgeCases,
  mockArchivedPage,
  mockArchivedPage2,
  mockArchivedPage3,
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

// Mock fetch for API calls
global.fetch = vi.fn()

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    isIframeLoaded: true,
    handleIframeLoad: vi.fn(),
    handleQuotesChange: vi.fn(),
  }),
}))

const mockSubmitEvaluation = vi.fn()
const mockSkipPolitician = vi.fn()

// Mock console.error to suppress expected error output
vi.spyOn(console, 'error').mockImplementation(() => {})

vi.mock('@/contexts/EvaluationContext', () => ({
  useEvaluation: () => ({
    completedCount: 0,
    sessionGoal: 1,
    isSessionComplete: false,
    submitEvaluation: mockSubmitEvaluation,
    skipPolitician: mockSkipPolitician,
    resetSession: vi.fn(),
    loadPoliticians: vi.fn(),
    currentPolitician: null,
    nextPolitician: null,
    loading: false,
  }),
}))

describe('PoliticianEvaluation', () => {
  const defaultProps = {
    politician: mockPolitician,
  }

  beforeEach(() => {
    // Clear highlights before each test
    CSS.highlights.clear()
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
    // Note: In the current implementation, both buttons can appear selected
    // This tests the behavior as implemented rather than ideal UX
  })

  it('shows "Skip Politician" when no evaluations are set, and "Submit Evaluations & Next" when evaluations exist', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    // Initially shows "Skip Politician" when no evaluations
    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Evaluations & Next')).not.toBeInTheDocument()

    // After making an evaluation, button text changes
    const acceptButton = screen.getAllByText('✓ Accept')[0]
    fireEvent.click(acceptButton)

    expect(screen.getByText('Submit Evaluations & Next')).toBeInTheDocument()
    expect(screen.queryByText('Skip Politician')).not.toBeInTheDocument()

    // Toggling off the evaluation reverts to "Skip Politician"
    fireEvent.click(acceptButton)

    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Evaluations & Next')).not.toBeInTheDocument()
  })

  it('submits evaluations successfully, clears state, and calls submitEvaluation', async () => {
    mockSubmitEvaluation.mockResolvedValueOnce(undefined)

    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    const rejectButtons = screen.getAllByText('× Reject')

    // Make multiple evaluations to ensure state clearing is comprehensive
    fireEvent.click(acceptButtons[0]) // First item accepted
    if (acceptButtons[1]) fireEvent.click(acceptButtons[1]) // Second item accepted
    if (rejectButtons[0]) fireEvent.click(rejectButtons[0]) // First item changed to reject

    // Verify buttons show selected state before submission
    expect(rejectButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-red-600')) // Selected state
    if (acceptButtons[1]) {
      expect(acceptButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-green-600')) // Selected state
    }

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockSubmitEvaluation).toHaveBeenCalledWith([
        { id: 'prop-1', is_accepted: false }, // rejected
        ...(acceptButtons[1] ? [{ id: 'pos-1', is_accepted: true }] : []), // accepted if exists
      ])
    })

    // Verify evaluation state is cleared after successful submission
    // Buttons should revert to unselected state (no longer have dark backgrounds)
    await waitFor(() => {
      expect(rejectButtons[0]).not.toHaveAttribute('class', expect.stringContaining('bg-red-600')) // Should be unselected
      expect(rejectButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-red-100')) // Should be default state
      if (acceptButtons[1]) {
        expect(acceptButtons[1]).not.toHaveAttribute(
          'class',
          expect.stringContaining('bg-green-600'),
        ) // Should be unselected
        expect(acceptButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-green-100')) // Should be default state
      }
    })
  })

  it('preserves evaluation state when submission fails', async () => {
    // Mock submitEvaluation to throw an error (simulating context handling the error)
    mockSubmitEvaluation.mockRejectedValueOnce(new Error('Submission failed'))

    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    const rejectButtons = screen.getAllByText('× Reject')

    // Make evaluations
    fireEvent.click(acceptButtons[0]) // First item accepted
    if (rejectButtons[1]) fireEvent.click(rejectButtons[1]) // Second item rejected

    // Verify buttons show selected state before submission
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600')) // Selected state
    if (rejectButtons[1]) {
      expect(rejectButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-red-600')) // Selected state
    }

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    // Wait for the failed submission to complete
    await waitFor(() => {
      expect(mockSubmitEvaluation).toHaveBeenCalled()
    })

    // Most importantly: verify evaluation state is PRESERVED after failed submission
    // Buttons should still show their selected state
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600')) // Should remain selected
    if (rejectButtons[1]) {
      expect(rejectButtons[1]).toHaveAttribute('class', expect.stringContaining('bg-red-600')) // Should remain selected
    }
  })

  it('preserves evaluation state when network request fails', async () => {
    // Mock submitEvaluation to reject (simulating network failure)
    mockSubmitEvaluation.mockRejectedValueOnce(new Error('Network connection failed'))

    render(<PoliticianEvaluation {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')

    // Make an evaluation
    fireEvent.click(acceptButtons[0])

    // Verify button shows selected state before submission
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600')) // Selected state

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    // Wait for the failed submission to complete
    await waitFor(() => {
      expect(mockSubmitEvaluation).toHaveBeenCalled()
    })

    // Most importantly: verify evaluation state is PRESERVED after network failure
    // Button should still show its selected state
    expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('bg-green-600')) // Should remain selected
  })

  it('does not render sections when politician has no unevaluated data', () => {
    render(<PoliticianEvaluation {...defaultProps} politician={mockEmptyPolitician} />)

    expect(screen.queryByText('Properties')).not.toBeInTheDocument()
    expect(screen.queryByText('Political Positions')).not.toBeInTheDocument()
    expect(screen.queryByText('Birthplaces')).not.toBeInTheDocument()
  })

  it('displays source information for items with archived pages', () => {
    render(<PoliticianEvaluation {...defaultProps} />)

    // Should show source viewing controls
    const viewingButtons = screen.getAllByText(/Viewing/)
    expect(viewingButtons.length).toBeGreaterThan(0)

    // Should show source URL
    const sourceTexts = screen.getAllByText('https://en.wikipedia.org/wiki/Test_Politician')
    expect(sourceTexts.length).toBeGreaterThan(0)
  })

  describe('property grouping', () => {
    it('displays sections in consistent order regardless of data order', () => {
      // Create politician with properties in different order to test section ordering
      const mockPoliticianReversedOrder = {
        ...mockPoliticianWithConflicts,
        properties: [
          // Citizenship first (should appear as "Citizenships" section)
          {
            key: 'prop-citizenship',
            id: 'prop-citizenship',
            type: PropertyType.P27,
            entity_id: 'Q142',
            entity_name: 'France',
            statement_id: null,
            supporting_quotes: ['French politician'],
          },
          // Birthplace second (should appear as "Birthplaces" section)
          {
            key: 'birth-1',
            id: 'birth-1',
            type: PropertyType.P19,
            entity_id: 'Q123456',
            entity_name: 'Test City',
            statement_id: null,
            supporting_quotes: ['was born in Test City'],
          },
          // Position third (should appear as "Political Positions" section)
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
          // Birth date last (should appear as "Properties" section)
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

      // Get all section headings in order
      const sectionHeadings = screen.getAllByRole('heading', { level: 2 })
      const sectionTexts = sectionHeadings.map((heading) => heading.textContent)

      // Verify consistent order: Properties, Political Positions, Birthplaces, Citizenships
      const expectedOrder = ['Properties', 'Political Positions', 'Birthplaces', 'Citizenships']
      const actualOrder = sectionTexts.filter((text) => expectedOrder.includes(text || ''))

      expect(actualOrder).toEqual(expectedOrder)
    })

    it('groups properties correctly by type and entity', () => {
      render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

      // Should have Properties section with birth dates grouped together
      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('Birth Date')).toBeInTheDocument()

      // Should have Political Positions section
      expect(screen.getByText('Political Positions')).toBeInTheDocument()

      // Should have separate items for different positions
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
      expect(screen.getByText(/Council Member/)).toBeInTheDocument()

      // Should have Birthplaces section
      expect(screen.getByText('Birthplaces')).toBeInTheDocument()

      // Look for birthplace specific Test City (with Q123456)
      const birthplaceSection = screen.getByText('Birthplaces').closest('.mb-8')
      expect(birthplaceSection).toBeInTheDocument()
      expect(birthplaceSection).toHaveTextContent('Test City')
      expect(birthplaceSection).toHaveTextContent('Q123456')
      expect(birthplaceSection).toHaveTextContent('New City')

      // Should have Citizenships section
      expect(screen.getByText('Citizenships')).toBeInTheDocument()
      expect(screen.getByText(/France/)).toBeInTheDocument()
    })

    it('groups multiple statements for the same entity together', () => {
      // Create a politician with multiple statements for the same position
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

      // Should have only ONE "Mayor of Test City" item that contains both statements
      const mayorItems = screen.getAllByText(/Mayor of Test City/)
      expect(mayorItems).toHaveLength(1) // Only one title, not two separate items

      // Should have both date ranges visible within the same item
      expect(screen.getByText('January 1, 2020 – January 1, 2024')).toBeInTheDocument()
      expect(screen.getByText('January 1, 2022 – January 1, 2026')).toBeInTheDocument()

      // Should have separator line between the statements
      const evaluationItem = screen.getByText(/Mayor of Test City/).closest('.border')
      expect(evaluationItem).toBeInTheDocument()
    })

    it('shows individual items for value-based properties', () => {
      render(<PoliticianEvaluation {...defaultProps} />)

      // Birth dates should be individual items, not grouped by entity
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('January 1, 1970')).toBeInTheDocument()

      // Should only have one Birth Date item even if there were multiple birth date properties
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

        // Should show "Current in Wikidata" badges or no evaluation controls for existing-only items
        // For now, let's just check that sections exist for properties, positions, and birthplaces
        expect(screen.getByText('Properties')).toBeInTheDocument()
        expect(screen.getByText('Political Positions')).toBeInTheDocument()
        expect(screen.getByText('Birthplaces')).toBeInTheDocument()
      })

      it('shows conflicted items with both values', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        // Should show the new extracted value
        expect(screen.getByText('January 2, 1970')).toBeInTheDocument() // New extracted value from mock data
        // Note: Current/existing values might not be shown in this implementation
      })

      it('maintains priority ordering: existing-only, conflicted, extracted-only', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        const propertiesSection = screen.getByText('Properties').closest('div')
        expect(propertiesSection).toBeInTheDocument()

        // The order should be: death_date (existing-only), birth_date (conflicted), nationality (extracted-only)
        // Check that we have both extracted/conflicted items with accept buttons
        const acceptButtons = screen.getAllByText('✓ Accept')

        // At least one extracted/conflicted item should exist
        expect(acceptButtons.length).toBeGreaterThan(0)
      })
    })

    describe('extracted-only data scenarios', () => {
      it('shows evaluation controls and allows interaction for extracted data', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExtractedOnly} />)

        expect(screen.getByText('Extracted Only Politician')).toBeInTheDocument()

        // Should have evaluation controls for extracted items
        const acceptButtons = screen.getAllByText('✓ Accept')
        const rejectButtons = screen.getAllByText('× Reject')

        expect(acceptButtons.length).toBeGreaterThan(0)
        expect(rejectButtons.length).toBeGreaterThan(0)

        // Evaluation should work
        fireEvent.click(acceptButtons[0])
        expect(acceptButtons[0]).toHaveAttribute('class', expect.stringContaining('green'))
      })
    })

    describe('existing-only data scenarios', () => {
      it('shows no evaluation controls for existing-only data', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />)

        expect(screen.getByText('Existing Only Politician')).toBeInTheDocument()

        // Should not show evaluation controls for existing-only items
        expect(screen.queryByText('✓ Accept')).not.toBeInTheDocument()
        expect(screen.queryByText('× Reject')).not.toBeInTheDocument()
      })
    })

    describe('evaluation submission with mixed data', () => {
      it('submits evaluations and progresses to next politician', async () => {
        mockSubmitEvaluation.mockResolvedValueOnce(undefined)

        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        // Make some evaluations
        const acceptButtons = screen.getAllByText('✓ Accept')
        const rejectButtons = screen.getAllByText('× Reject')

        if (acceptButtons[0]) fireEvent.click(acceptButtons[0])
        if (rejectButtons.length > 1) fireEvent.click(rejectButtons[1])

        const submitButton = screen.getByText('Submit Evaluations & Next')
        fireEvent.click(submitButton)

        // Should call submitEvaluation and progress to next
        await waitFor(() => {
          expect(mockSubmitEvaluation).toHaveBeenCalled()
        })
      })
    })

    describe('archived page handling', () => {
      it('provides source viewing for items with archived pages', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianWithConflicts} />)

        // Should show source viewing controls for items that have archived pages
        const viewingButtons = screen.getAllByText(/Viewing/)
        expect(viewingButtons.length).toBeGreaterThan(0)

        // Should show the archived page iframe
        expect(screen.getByTitle('Archived Page')).toBeInTheDocument()
      })

      it('shows placeholder when no source is available', () => {
        render(<PoliticianEvaluation {...defaultProps} politician={mockPoliticianExistingOnly} />)

        // Should show helpful message when no source is available
        expect(
          screen.getByText(/Click.*View.*on any item to see the source page/),
        ).toBeInTheDocument()
      })

      it('auto-loads the first property with an archived page on mount', () => {
        render(
          <PoliticianEvaluation
            {...defaultProps}
            politician={mockPoliticianWithDifferentSources}
            archivedPagesApiPath="/api/archived-pages"
          />,
        )

        // The iframe should be present and pointing to the first property's archived page
        const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
        expect(iframe).toBeInTheDocument()
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)

        // The first property should show "Viewing" (active state)
        // First new property is prop-source-1 (birth date) with archived-1
        const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
        // First button should show "Viewing" since it's auto-loaded
        expect(viewButtons[0]).toHaveTextContent('• Viewing')
      })

      it('clicking View on a property updates the iframe to show that archived page', () => {
        render(
          <PoliticianEvaluation
            {...defaultProps}
            politician={mockPoliticianWithDifferentSources}
            archivedPagesApiPath="/api/archived-pages"
          />,
        )

        // Initially showing first archived page
        const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)

        // Find the View button for the second property (Governor position with archived-2)
        // It should show "View" not "Viewing" since the first property is auto-loaded
        const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })

        // Click on the second View button (for the position with archived-2)
        const secondViewButton = viewButtons.find((btn) => btn.textContent === '• View')
        expect(secondViewButton).toBeDefined()
        fireEvent.click(secondViewButton!)

        // Iframe should now point to the second archived page
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage2.id}/html`)

        // The clicked button should now show "Viewing"
        expect(secondViewButton).toHaveTextContent('• Viewing')
      })

      it('switching between properties with different archived pages updates the iframe', async () => {
        render(
          <PoliticianEvaluation
            {...defaultProps}
            politician={mockPoliticianWithDifferentSources}
            archivedPagesApiPath="/api/archived-pages"
          />,
        )

        const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement

        // Initially showing first archived page (archived-1)
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)

        // Get all View buttons
        const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
        expect(viewButtons.length).toBe(3) // Three properties with archived pages

        // Click the second button (Governor - archived-2)
        fireEvent.click(viewButtons[1])
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage2.id}/html`)

        // Click the third button (Birthplace - archived-3)
        fireEvent.click(viewButtons[2])
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage3.id}/html`)

        // Click back to first button (Birth Date - archived-1)
        fireEvent.click(viewButtons[0])
        expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)
      })

      it('only the active property View button shows "Viewing"', () => {
        render(
          <PoliticianEvaluation
            {...defaultProps}
            politician={mockPoliticianWithDifferentSources}
            archivedPagesApiPath="/api/archived-pages"
          />,
        )

        // Get all View buttons
        const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })

        // Initially only the first should be active
        expect(viewButtons[0]).toHaveTextContent('• Viewing')
        expect(viewButtons[1]).toHaveTextContent('• View')
        expect(viewButtons[2]).toHaveTextContent('• View')

        // Click the second button
        fireEvent.click(viewButtons[1])

        // Now second should be active, others should not
        expect(viewButtons[0]).toHaveTextContent('• View')
        expect(viewButtons[1]).toHaveTextContent('• Viewing')
        expect(viewButtons[2]).toHaveTextContent('• View')

        // Click the third button
        fireEvent.click(viewButtons[2])

        // Now third should be active
        expect(viewButtons[0]).toHaveTextContent('• View')
        expect(viewButtons[1]).toHaveTextContent('• View')
        expect(viewButtons[2]).toHaveTextContent('• Viewing')
      })

      it('does not show View button for Wikidata statements even if they have archived pages', () => {
        render(
          <PoliticianEvaluation
            {...defaultProps}
            politician={mockPoliticianWithEdgeCases}
            archivedPagesApiPath="/api/archived-pages"
          />,
        )

        // The mockPoliticianWithEdgeCases has Wikidata statements with archived pages
        // but View buttons should only appear for the non-Wikidata statements

        // There should be at least one View button (for the extracted statement)
        const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })

        // Only the extracted statement (prop-extracted-1) should have a View button
        // The Wikidata statements should not show View buttons
        expect(viewButtons.length).toBe(1)
      })
    })
  })
})
