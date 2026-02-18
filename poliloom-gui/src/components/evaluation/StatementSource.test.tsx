import { render, screen, fireEvent } from '@testing-library/react'
import { StatementSource } from './StatementSource'
import { vi } from 'vitest'
import { PropertyReference } from '@/types'

const mockOnShowArchived = vi.fn()
const mockOnHover = vi.fn()

const mockArchivedPage = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  content_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
}

const mockSource: PropertyReference = {
  id: 'ref-1',
  archived_page: mockArchivedPage,
  supporting_quotes: ['test quote'],
}

const mockSourceNoQuotes: PropertyReference = {
  id: 'ref-2',
  archived_page: mockArchivedPage,
}

describe('StatementSource', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('View button behavior', () => {
    it('renders View button when sources exist and not a Wikidata statement', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toBeInTheDocument()
      expect(viewButton).toHaveTextContent('• View')
    })

    it('shows "Viewing" text when activeArchivedPageId matches', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId="archived-1"
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /Viewing/ })
      expect(viewButton).toBeInTheDocument()
      expect(viewButton).toHaveTextContent('• Viewing')
    })

    it('shows "View" text when activeArchivedPageId does not match', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId="other-page"
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toHaveTextContent('• View')
      expect(viewButton).not.toHaveTextContent('Viewing')
    })

    it('calls onShowArchived with ref when View button is clicked', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      fireEvent.click(viewButton)

      expect(mockOnShowArchived).toHaveBeenCalledTimes(1)
      expect(mockOnShowArchived).toHaveBeenCalledWith(mockSource)
    })

    it('does not render when sources is empty', () => {
      render(
        <StatementSource
          sources={[]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      expect(screen.queryByRole('button', { name: /View/ })).not.toBeInTheDocument()
    })

    it('does not render when isWikidataStatement is true', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={true}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      expect(screen.queryByRole('button', { name: /View/ })).not.toBeInTheDocument()
    })

    it('applies active styling to button when activeArchivedPageId matches', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId="archived-1"
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /Viewing/ })
      expect(viewButton).toHaveAttribute('class', expect.stringContaining('bg-accent'))
    })
  })

  describe('supporting quotes display', () => {
    it('renders supporting quotes when provided', () => {
      const sourceWithQuotes: PropertyReference = {
        id: 'ref-quotes',
        archived_page: mockArchivedPage,
        supporting_quotes: ['first quote', 'second quote'],
      }

      render(
        <StatementSource
          sources={[sourceWithQuotes]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      expect(screen.getByText('"first quote"')).toBeInTheDocument()
      expect(screen.getByText('"second quote"')).toBeInTheDocument()
    })

    it('does not render quotes section when supportingQuotes is undefined', () => {
      render(
        <StatementSource
          sources={[mockSourceNoQuotes]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const list = screen.queryByRole('list')
      expect(list).not.toBeInTheDocument()
    })

    it('does not render quotes section when supportingQuotes is empty', () => {
      const sourceEmptyQuotes: PropertyReference = {
        id: 'ref-empty',
        archived_page: mockArchivedPage,
        supporting_quotes: [],
      }

      render(
        <StatementSource
          sources={[sourceEmptyQuotes]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const list = screen.queryByRole('list')
      expect(list).not.toBeInTheDocument()
    })
  })

  describe('hover behavior', () => {
    it('calls onHover when mouse enters component', () => {
      const { container } = render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const rootDiv = container.firstChild as Element
      fireEvent.mouseEnter(rootDiv)

      expect(mockOnHover).toHaveBeenCalledTimes(1)
    })
  })

  describe('URL display', () => {
    it('renders archived page URL as a link', () => {
      render(
        <StatementSource
          sources={[mockSource]}
          isWikidataStatement={false}
          activeArchivedPageId={null}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const link = screen.getByRole('link', { name: mockArchivedPage.url })
      expect(link).toHaveAttribute('href', mockArchivedPage.url)
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    })
  })
})
