import { render, screen, fireEvent } from '@testing-library/react'
import { PropertyDisplay } from './PropertyDisplay'
import { PropertyType, Property } from '@/types'
import { vi } from 'vitest'

const mockOnAction = vi.fn()
const mockOnShowSource = vi.fn()
const mockOnHover = vi.fn()

const mockSource = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  url_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done' as const,
  language_qids: [] as string[],
}

const baseProperty: Property = {
  id: 'test-1',
  type: PropertyType.P569,
  statement_id: null,
  sources: [],
}

describe('PropertyDisplay', () => {
  it('renders birth date with formatted value', () => {
    const property: Property = {
      ...baseProperty,
      type: PropertyType.P569,
      value: '+1990-05-15T00:00:00Z',
      value_precision: 11,
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('May 15, 1990')).toBeInTheDocument()
  })

  it('renders position with date range from qualifiers', () => {
    const property: Property = {
      ...baseProperty,
      type: PropertyType.P39,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-12-31T00:00:00Z', precision: 11 } } }],
      },
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('January 1, 2020 – December 31, 2024')).toBeInTheDocument()
  })

  it('shows no timeframe message for position without dates', () => {
    const property: Property = {
      ...baseProperty,
      type: PropertyType.P39,
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('No timeframe specified')).toBeInTheDocument()
  })

  it('renders empty content for birthplace properties', () => {
    const property: Property = {
      ...baseProperty,
      type: PropertyType.P19,
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    // Should render evaluation actions
    expect(screen.getByText('✓ Accept')).toBeInTheDocument()
    expect(screen.getByText('× Reject')).toBeInTheDocument()
  })

  it('calls onHover when mouse enters component', () => {
    const property: Property = { ...baseProperty }

    const { container } = render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    const divWithHover = container.querySelector('.space-y-2')
    fireEvent.mouseEnter(divWithHover as Element)

    expect(mockOnHover).toHaveBeenCalledWith(property)
  })

  it('shows StatementSource for non-Wikidata statements', () => {
    const property: Property = {
      ...baseProperty,
      statement_id: null,
      sources: [
        {
          id: 'ref-1',
          source: mockSource,
          supporting_quotes: ['Test proof line'],
        },
      ],
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('"Test proof line"')).toBeInTheDocument()
  })

  it('shows WikidataMetadata only when deprecating existing Wikidata statements', () => {
    const property: Property = {
      ...baseProperty,
      statement_id: 'Q123$abc-def',
      references: [{ url: 'https://example.com', title: 'Reference' }],
      sources: [],
    }

    // Initially, metadata is not shown
    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('Existing data')).toBeInTheDocument()
    expect(screen.queryByText('References')).not.toBeInTheDocument()
  })

  it('shows WikidataMetadata when user is deprecating a statement', () => {
    const property: Property = {
      ...baseProperty,
      statement_id: 'Q123$abc-def',
      references: [{ url: 'https://example.com', title: 'Reference' }],
      sources: [],
      evaluation: false, // Deprecating
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onViewSource={mockOnShowSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('References')).toBeInTheDocument()
    expect(screen.getByText('⚠️')).toBeInTheDocument()
  })

  describe('Wikidata statements', () => {
    it('hides Deprecate button when showExistingStatementActions is false', () => {
      const property: Property = {
        ...baseProperty,
        statement_id: 'Q123$abc-def',
        sources: [],
      }

      render(<PropertyDisplay property={property} onAction={mockOnAction} activeSourceId={null} />)

      expect(screen.queryByRole('button', { name: /Deprecate/ })).not.toBeInTheDocument()
      expect(screen.getByText('Existing data')).toBeInTheDocument()
    })
  })

  describe('new data statements', () => {
    it('shows Accept/Reject buttons when source is visible', () => {
      const property: Property = {
        ...baseProperty,
        sources: [
          {
            id: 'ref-1',
            source: mockSource,
            supporting_quotes: [],
          },
        ],
      }

      render(
        <PropertyDisplay property={property} onAction={mockOnAction} activeSourceId="archived-1" />,
      )

      expect(screen.getByRole('button', { name: /Accept/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Reject/ })).toBeInTheDocument()
    })

    it('hides buttons when source is not visible', () => {
      const property: Property = {
        ...baseProperty,
        sources: [
          {
            id: 'ref-1',
            source: mockSource,
            supporting_quotes: [],
          },
        ],
      }

      render(
        <PropertyDisplay property={property} onAction={mockOnAction} activeSourceId="other-page" />,
      )

      expect(screen.queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reject/ })).not.toBeInTheDocument()
      expect(screen.getByText('View source to evaluate')).toBeInTheDocument()
    })
  })

  describe('user-added properties', () => {
    it('shows Remove button instead of Reject and hides Accept', () => {
      const property: Property = {
        ...baseProperty,
        userAdded: true,
        evaluation: true,
        sources: [],
      }

      render(<PropertyDisplay property={property} onAction={mockOnAction} activeSourceId={null} />)

      expect(screen.getByRole('button', { name: /Remove/ })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reject/ })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
    })

    it('calls onAction with reject when Remove is clicked', () => {
      const property: Property = {
        ...baseProperty,
        userAdded: true,
        evaluation: true,
        sources: [],
      }

      render(<PropertyDisplay property={property} onAction={mockOnAction} activeSourceId={null} />)

      fireEvent.click(screen.getByRole('button', { name: /Remove/ }))
      expect(mockOnAction).toHaveBeenCalledWith('test-1', 'reject')
    })
  })

  describe('auto-open behavior', () => {
    it('auto-opens the references panel when shouldAutoOpen and deprecating', () => {
      const property: Property = {
        ...baseProperty,
        statement_id: 'Q123$abc-def',
        references: [{ url: 'https://example.com', title: 'Reference' }],
        sources: [],
        evaluation: false,
      }

      render(
        <PropertyDisplay
          property={property}
          onAction={mockOnAction}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
          activeSourceId={null}
          shouldAutoOpen
        />,
      )

      // Panel is auto-opened: the "will be lost" banner renders and the collapsed
      // warning indicator is hidden.
      expect(screen.getByText('Metadata will be lost ⚠️')).toBeInTheDocument()
      expect(screen.queryByText('⚠️')).not.toBeInTheDocument()
    })

    it('auto-opens the qualifiers panel when shouldAutoOpen and deprecating', () => {
      const property: Property = {
        ...baseProperty,
        type: PropertyType.P39,
        statement_id: 'Q123$abc-def',
        qualifiers: {
          P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        },
        sources: [],
        evaluation: false,
      }

      render(
        <PropertyDisplay
          property={property}
          onAction={mockOnAction}
          onViewSource={mockOnShowSource}
          onHover={mockOnHover}
          activeSourceId={null}
          shouldAutoOpen
        />,
      )

      expect(screen.getByText('Metadata will be lost ⚠️')).toBeInTheDocument()
      expect(screen.queryByText('⚠️')).not.toBeInTheDocument()
    })

    it('resets an auto-opened panel when the statement is restored', () => {
      const property: Property = {
        ...baseProperty,
        statement_id: 'Q123$abc-def',
        references: [{ url: 'https://example.com', title: 'Reference' }],
        sources: [],
        evaluation: false,
      }
      const props = {
        onAction: mockOnAction,
        activeSourceId: null,
      }
      const { rerender } = render(<PropertyDisplay property={property} shouldAutoOpen {...props} />)

      expect(screen.getByText('Metadata will be lost ⚠️')).toBeInTheDocument()

      rerender(<PropertyDisplay property={property} shouldAutoOpen={false} {...props} />)
      rerender(
        <PropertyDisplay
          property={{ ...property, evaluation: true }}
          shouldAutoOpen={false}
          {...props}
        />,
      )
      rerender(<PropertyDisplay property={property} shouldAutoOpen={false} {...props} />)

      expect(screen.queryByText('Metadata will be lost ⚠️')).not.toBeInTheDocument()
      expect(screen.getByText('⚠️')).toBeInTheDocument()
    })
  })
})
