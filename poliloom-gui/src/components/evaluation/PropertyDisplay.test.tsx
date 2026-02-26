import { render, screen, fireEvent } from '@testing-library/react'
import { PropertyDisplay } from './PropertyDisplay'
import { PropertyType, PropertyWithEvaluation } from '@/types'
import { vi } from 'vitest'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

const mockOnAction = vi.fn()
const mockOnShowArchived = vi.fn()
const mockOnHover = vi.fn()

const mockArchivedPage = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  content_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
}

const baseProperty: PropertyWithEvaluation = {
  key: 'test-1',
  id: 'test-1',
  type: PropertyType.P569,
  statement_id: null,
  sources: [],
}

describe('PropertyDisplay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders birth date with formatted value', () => {
    const property: PropertyWithEvaluation = {
      ...baseProperty,
      type: PropertyType.P569,
      value: '+1990-05-15T00:00:00Z',
      value_precision: 11,
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('May 15, 1990')).toBeInTheDocument()
  })

  it('renders position with date range from qualifiers', () => {
    const property: PropertyWithEvaluation = {
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
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('January 1, 2020 – December 31, 2024')).toBeInTheDocument()
  })

  it('shows no timeframe message for position without dates', () => {
    const property: PropertyWithEvaluation = {
      ...baseProperty,
      type: PropertyType.P39,
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('No timeframe specified')).toBeInTheDocument()
  })

  it('renders empty content for birthplace properties', () => {
    const property: PropertyWithEvaluation = {
      ...baseProperty,
      type: PropertyType.P19,
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    // Should render evaluation actions
    expect(screen.getByText('✓ Accept')).toBeInTheDocument()
    expect(screen.getByText('× Reject')).toBeInTheDocument()
  })

  it('calls onHover when mouse enters component', () => {
    const property: PropertyWithEvaluation = { ...baseProperty }

    const { container } = render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    const divWithHover = container.querySelector('.space-y-2')
    fireEvent.mouseEnter(divWithHover as Element)

    expect(mockOnHover).toHaveBeenCalledWith(property)
  })

  it('shows StatementSource for non-Wikidata statements', () => {
    const property: PropertyWithEvaluation = {
      ...baseProperty,
      statement_id: null,
      sources: [
        {
          id: 'ref-1',
          archived_page: mockArchivedPage,
          supporting_quotes: ['Test proof line'],
        },
      ],
    }

    render(
      <PropertyDisplay
        property={property}
        onAction={mockOnAction}
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('"Test proof line"')).toBeInTheDocument()
  })

  it('shows WikidataMetadata only when deprecating existing Wikidata statements', () => {
    const property: PropertyWithEvaluation = {
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
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('Existing data')).toBeInTheDocument()
    expect(screen.queryByText('References')).not.toBeInTheDocument()
  })

  it('shows WikidataMetadata when user is deprecating a statement', () => {
    const property: PropertyWithEvaluation = {
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
        onShowArchived={mockOnShowArchived}
        onHover={mockOnHover}
        activeArchivedPageId={null}
      />,
    )

    expect(screen.getByText('References')).toBeInTheDocument()
    expect(screen.getByText('⚠️')).toBeInTheDocument()
  })
})
