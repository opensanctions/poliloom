import { render, screen, fireEvent } from '@testing-library/react'
import { PropertyDisplay } from './PropertyDisplay'
import { PropertyType } from '@/types'
import { vi } from 'vitest'

const mockOnAction = vi.fn()
const mockOnShowArchived = vi.fn()
const mockOnHover = vi.fn()

const baseProperty = {
  id: 'test-1',
  type: PropertyType.P569,
  statement_id: null,
}

describe('PropertyDisplay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders birth date with formatted value', () => {
    const property = {
      ...baseProperty,
      type: PropertyType.P569,
      value: '+1990-05-15T00:00:00Z',
      value_precision: 11,
    }

    render(
      <PropertyDisplay
        property={property}
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('May 15, 1990')).toBeInTheDocument()
  })

  it('renders position with date range from qualifiers', () => {
    const property = {
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
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('January 1, 2020 – December 31, 2024')).toBeInTheDocument()
  })

  it('shows no timeframe message for position without dates', () => {
    const property = {
      ...baseProperty,
      type: PropertyType.P39,
    }

    render(
      <PropertyDisplay
        property={property}
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('No timeframe specified')).toBeInTheDocument()
  })

  it('renders empty content for birthplace properties', () => {
    const property = {
      ...baseProperty,
      type: PropertyType.P19,
    }

    render(
      <PropertyDisplay
        property={property}
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    // Should render evaluation actions
    expect(screen.getByText('✓ Confirm')).toBeInTheDocument()
    expect(screen.getByText('× Discard')).toBeInTheDocument()
  })

  it('calls onHover when mouse enters component', () => {
    const property = { ...baseProperty }

    const { container } = render(
      <PropertyDisplay
        property={property}
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    fireEvent.mouseEnter(container.firstChild as Element)

    expect(mockOnHover).toHaveBeenCalledWith(property)
  })

  it('shows StatementSource for non-Wikidata statements', () => {
    const property = {
      ...baseProperty,
      statement_id: null,
      proof_line: 'Test proof line',
    }

    render(
      <PropertyDisplay
        property={property}
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('"Test proof line"')).toBeInTheDocument()
  })

  it('shows WikidataMetadata for existing Wikidata statements', () => {
    const property = {
      ...baseProperty,
      statement_id: 'Q123$abc-def',
      references: [{ url: 'https://example.com', title: 'Reference' }],
    }

    render(
      <PropertyDisplay
        property={property}
        evaluations={new Map()}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('Current in Wikidata')).toBeInTheDocument()
    expect(screen.getByText('References')).toBeInTheDocument()
  })
})
