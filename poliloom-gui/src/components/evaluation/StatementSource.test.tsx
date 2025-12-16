import { render, screen, fireEvent } from '@testing-library/react'
import { StatementSource } from './StatementSource'
import { vi } from 'vitest'

const mockOnShowArchived = vi.fn()
const mockOnHover = vi.fn()

const mockArchivedPage = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  content_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
}

describe('StatementSource', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('View button behavior', () => {
    it('renders View button when archivedPage exists and not a Wikidata statement', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toBeInTheDocument()
      expect(viewButton).toHaveTextContent('• View')
    })

    it('shows "Viewing" text when isActive is true', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={true}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /Viewing/ })
      expect(viewButton).toBeInTheDocument()
      expect(viewButton).toHaveTextContent('• Viewing')
    })

    it('shows "View" text when isActive is false', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toHaveTextContent('• View')
      expect(viewButton).not.toHaveTextContent('Viewing')
    })

    it('calls onShowArchived when View button is clicked', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      fireEvent.click(viewButton)

      expect(mockOnShowArchived).toHaveBeenCalledTimes(1)
    })

    it('does not render View button when archivedPage is null', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={null}
          isWikidataStatement={false}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      expect(screen.queryByRole('button', { name: /View/ })).not.toBeInTheDocument()
    })

    it('does not render View button when isWikidataStatement is true', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={true}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      expect(screen.queryByRole('button', { name: /View/ })).not.toBeInTheDocument()
    })

    it('applies active styling to button when isActive is true', () => {
      render(
        <StatementSource
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={true}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /Viewing/ })
      // The Button component with active=true and variant=info gets 'bg-accent' class
      expect(viewButton).toHaveAttribute('class', expect.stringContaining('bg-accent'))
    })
  })

  describe('supporting quotes display', () => {
    it('renders supporting quotes when provided', () => {
      render(
        <StatementSource
          supportingQuotes={['first quote', 'second quote']}
          archivedPage={null}
          isWikidataStatement={false}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      expect(screen.getByText('"first quote"')).toBeInTheDocument()
      expect(screen.getByText('"second quote"')).toBeInTheDocument()
    })

    it('does not render quotes section when supportingQuotes is null', () => {
      render(
        <StatementSource
          supportingQuotes={null}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
          onShowArchived={mockOnShowArchived}
          onHover={mockOnHover}
        />,
      )

      const list = screen.queryByRole('list')
      expect(list).not.toBeInTheDocument()
    })

    it('does not render quotes section when supportingQuotes is empty', () => {
      render(
        <StatementSource
          supportingQuotes={[]}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
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
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
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
          supportingQuotes={['test quote']}
          archivedPage={mockArchivedPage}
          isWikidataStatement={false}
          isActive={false}
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
