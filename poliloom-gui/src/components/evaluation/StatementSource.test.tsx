import { render, screen, fireEvent } from '@testing-library/react'
import { StatementSource } from './StatementSource'
import { vi } from 'vitest'
import { ActionEvidence, SourceResponse } from '@/types'

const mockOnShowSource = vi.fn()
const mockOnHover = vi.fn()

const mockSource: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  url_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const mockEvidence: ActionEvidence = {
  id: 'ev-1',
  source: mockSource,
  supporting_quotes: ['test quote'],
}

const mockEvidenceNoQuotes: ActionEvidence = {
  id: 'ev-2',
  source: mockSource,
  supporting_quotes: null,
}

describe('StatementSource', () => {
  describe('View button behavior', () => {
    it('renders View button when evidence exists', () => {
      render(
        <StatementSource
          evidence={[mockEvidence]}
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
          evidence={[mockEvidence]}
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
          evidence={[mockEvidence]}
          activeSourceId="other-page"
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      expect(viewButton).toHaveTextContent('• View')
      expect(viewButton).not.toHaveTextContent('Viewing')
    })

    it('calls onViewSource with the evidence source and quotes when View is clicked', () => {
      render(
        <StatementSource
          evidence={[mockEvidence]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const viewButton = screen.getByRole('button', { name: /View/ })
      fireEvent.click(viewButton)

      expect(mockOnShowSource).toHaveBeenCalledTimes(1)
      expect(mockOnShowSource).toHaveBeenCalledWith(mockSource, mockEvidence.supporting_quotes)
    })

    it('does not render when evidence is empty', () => {
      render(
        <StatementSource
          evidence={[]}
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
          evidence={[mockEvidence]}
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
      const evidenceWithQuotes: ActionEvidence = {
        id: 'ev-quotes',
        source: mockSource,
        supporting_quotes: ['first quote', 'second quote'],
      }

      render(
        <StatementSource
          evidence={[evidenceWithQuotes]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      expect(screen.getByText('"first quote"')).toBeInTheDocument()
      expect(screen.getByText('"second quote"')).toBeInTheDocument()
    })

    it('does not render quotes section when supporting_quotes is null', () => {
      render(
        <StatementSource
          evidence={[mockEvidenceNoQuotes]}
          activeSourceId={null}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
        />,
      )

      const list = screen.queryByRole('list')
      expect(list).not.toBeInTheDocument()
    })

    it('does not render quotes section when supporting_quotes is empty', () => {
      const evidenceEmptyQuotes: ActionEvidence = {
        id: 'ev-empty',
        source: mockSource,
        supporting_quotes: [],
      }

      render(
        <StatementSource
          evidence={[evidenceEmptyQuotes]}
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
          evidence={[mockEvidence]}
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
          evidence={[mockEvidence]}
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
