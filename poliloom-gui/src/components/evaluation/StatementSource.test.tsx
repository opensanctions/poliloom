import { render, screen, fireEvent } from '@testing-library/react'
import { StatementSource } from './StatementSource'
import { vi } from 'vitest'
import { SourceResponse, PropertyReference } from '@/types'

const mockOnShowSource = vi.fn()
const mockOnHover = vi.fn()

const mockSource: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  url_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
}

const mockRef: PropertyReference = {
  id: 'ref-1',
  source: mockSource,
  supporting_quotes: ['test quote'],
}

const mockRefNoQuotes: PropertyReference = {
  id: 'ref-2',
  source: mockSource,
}

describe('StatementSource', () => {
  describe('View button behavior', () => {
    it('renders View button when sources exist', () => {
      render(
        <StatementSource
          sources={[mockRef]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toBeInTheDocument()
      expect(viewButton).toHaveTextContent('• View')
    })

    it('shows "Viewing" text when activeSourceId matches', () => {
      render(
        <StatementSource
          sources={[mockRef]}
          activeSourceId="archived-1"
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /Viewing/ })
      expect(viewButton).toBeInTheDocument()
      expect(viewButton).toHaveTextContent('• Viewing')
    })

    it('shows "View" text when activeSourceId does not match', () => {
      render(
        <StatementSource
          sources={[mockRef]}
          activeSourceId="other-page"
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toHaveTextContent('• View')
      expect(viewButton).not.toHaveTextContent('Viewing')
    })

    it('calls onViewSource with ref when View button is clicked', () => {
      render(
        <StatementSource
          sources={[mockRef]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      fireEvent.click(viewButton)

      expect(mockOnShowSource).toHaveBeenCalledTimes(1)
      expect(mockOnShowSource).toHaveBeenCalledWith(mockRef.source, mockRef.supporting_quotes)
    })

    it('does not render when sources is empty', () => {
      render(
        <StatementSource
          sources={[]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      expect(screen.queryByRole('button', { name: /View/ })).not.toBeInTheDocument()
    })

    it('applies active styling to button when activeSourceId matches', () => {
      render(
        <StatementSource
          sources={[mockRef]}
          activeSourceId="archived-1"
          onViewSource={mockOnShowSource}
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
        source: mockSource,
        supporting_quotes: ['first quote', 'second quote'],
      }

      render(
        <StatementSource
          sources={[sourceWithQuotes]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      expect(screen.getByText('"first quote"')).toBeInTheDocument()
      expect(screen.getByText('"second quote"')).toBeInTheDocument()
    })

    it('does not render quotes section when supportingQuotes is undefined', () => {
      render(
        <StatementSource
          sources={[mockRefNoQuotes]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const list = screen.queryByRole('list')
      expect(list).not.toBeInTheDocument()
    })

    it('does not render quotes section when supportingQuotes is empty', () => {
      const sourceEmptyQuotes: PropertyReference = {
        id: 'ref-empty',
        source: mockSource,
        supporting_quotes: [],
      }

      render(
        <StatementSource
          sources={[sourceEmptyQuotes]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
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
          sources={[mockRef]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const rootDiv = container.firstChild as Element
      fireEvent.mouseEnter(rootDiv)

      expect(mockOnHover).toHaveBeenCalledTimes(1)
    })
  })

  describe('URL display', () => {
    it('renders source URL as a link', () => {
      render(
        <StatementSource
          sources={[mockRef]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const link = screen.getByRole('link', { name: mockSource.url })
      expect(link).toHaveAttribute('href', mockSource.url)
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    })
  })
})
