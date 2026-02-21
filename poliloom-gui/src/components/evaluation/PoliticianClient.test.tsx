import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  screen,
  fireEvent,
  waitFor,
  render,
  mockSubmitAndAdvance,
  mockRouterPush,
  mockFetch,
} from '@/test/test-utils'
import { PoliticianClient } from './PoliticianClient'
import { mockPolitician, mockPoliticianWithConflicts } from '@/test/mock-data'

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

describe('PoliticianClient', () => {
  const defaultProps = {
    politician: mockPolitician,
  }

  beforeEach(() => {
    CSS.highlights.clear()
    mockSubmitAndAdvance.mockClear()
    mockRouterPush.mockClear()
    mockFetch.mockClear()
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'OK', errors: [] }),
    })
  })

  it('renders politician name and wikidata id', () => {
    render(<PoliticianClient {...defaultProps} />)

    expect(screen.getByText('Test Politician')).toBeInTheDocument()
    expect(screen.getByText('(Q987654)')).toBeInTheDocument()
  })

  it('renders properties section with property details', () => {
    render(<PoliticianClient {...defaultProps} />)

    expect(screen.getByText('Properties')).toBeInTheDocument()
    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('January 1, 1970')).toBeInTheDocument()
    expect(screen.getByText('"born on January 1, 1970"')).toBeInTheDocument()
  })

  it('renders positions section with position details', () => {
    render(<PoliticianClient {...defaultProps} />)

    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
  })

  it('renders birthplaces section with birthplace details', () => {
    render(<PoliticianClient {...defaultProps} />)

    expect(screen.getByText('Birthplaces')).toBeInTheDocument()
  })

  it('allows users to evaluate items by accepting or rejecting', () => {
    render(<PoliticianClient {...defaultProps} />)

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    const rejectButton = screen.getAllByText('× Reject')[0]

    fireEvent.click(acceptButton)
    expect(acceptButton).toHaveAttribute('class', expect.stringContaining('bg-success'))

    fireEvent.click(rejectButton)
    expect(rejectButton).toHaveAttribute('class', expect.stringContaining('bg-danger'))
  })

  it('shows session progress in session mode', () => {
    render(<PoliticianClient {...defaultProps} />)

    expect(screen.getByText(/Progress:/)).toBeInTheDocument()
    expect(screen.getByText('0 / 5')).toBeInTheDocument()
  })

  it('shows "Skip Politician" when no evaluations and "Submit Evaluations & Next" when evaluations exist', () => {
    render(<PoliticianClient {...defaultProps} />)

    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Evaluations & Next')).not.toBeInTheDocument()

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    fireEvent.click(acceptButton)

    expect(screen.getByText('Submit Evaluations & Next')).toBeInTheDocument()
    expect(screen.queryByText('Skip Politician')).not.toBeInTheDocument()
  })

  it('submits evaluations via API and advances session', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'OK', errors: [] }),
    })
    mockSubmitAndAdvance.mockReturnValue({ sessionComplete: false })

    render(<PoliticianClient {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    fireEvent.click(acceptButtons[0])

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/evaluations',
        expect.objectContaining({
          method: 'POST',
        }),
      )
      expect(mockSubmitAndAdvance).toHaveBeenCalled()
    })
  })

  it('redirects to /session/complete on session completion when stats unlocked', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'OK', errors: [] }),
    })
    mockSubmitAndAdvance.mockReturnValue({ sessionComplete: true })

    render(<PoliticianClient {...defaultProps} />)

    const acceptButtons = screen.getAllByText('✓ Accept')
    fireEvent.click(acceptButtons[0])

    const submitButton = screen.getByText('Submit Evaluations & Next')
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/session/complete')
    })
  })

  describe('property grouping', () => {
    it('groups properties correctly by type and entity', () => {
      render(<PoliticianClient {...defaultProps} politician={mockPoliticianWithConflicts} />)

      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('Political Positions')).toBeInTheDocument()
      expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
      expect(screen.getByText(/Council Member/)).toBeInTheDocument()
      expect(screen.getByText('Birthplaces')).toBeInTheDocument()
      expect(screen.getByText('Citizenships')).toBeInTheDocument()
    })
  })

  describe('archived page handling', () => {
    it('provides source viewing for items with archived pages', () => {
      render(<PoliticianClient {...defaultProps} politician={mockPoliticianWithConflicts} />)

      const viewingButtons = screen.getAllByText(/Viewing/)
      expect(viewingButtons.length).toBeGreaterThan(0)

      expect(screen.getByTitle('Archived Page')).toBeInTheDocument()
    })
  })
})
