import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PropertiesEvaluation } from './PropertiesEvaluation'
import { PropertyType, Property, SourceResponse } from '@/types'

const mockOnAction = vi.fn()
const mockOnViewSource = vi.fn()
const mockOnHover = vi.fn()
const mockOnAddProperty = vi.fn()

const mockSource: SourceResponse = {
  id: 'src-1',
  url: 'https://example.com',
  url_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
}

const birthDate: Property = {
  id: 'prop-1',
  type: PropertyType.P569,
  value: '+1990-05-15T00:00:00Z',
  value_precision: 11,
  statement_id: null,
  sources: [{ id: 'ref-1', source: mockSource, supporting_quotes: ['born May 15'] }],
}

const deathDate: Property = {
  id: 'prop-2',
  type: PropertyType.P570,
  value: '+2020-01-01T00:00:00Z',
  value_precision: 11,
  statement_id: null,
  sources: [],
}

const position: Property = {
  id: 'prop-3',
  type: PropertyType.P39,
  entity_id: 'Q200',
  entity_name: 'Governor',
  statement_id: null,
  qualifiers: {
    P580: [{ datavalue: { value: { time: '+2018-01-01T00:00:00Z', precision: 11 } } }],
  },
  sources: [{ id: 'ref-2', source: mockSource }],
}

const birthplace: Property = {
  id: 'prop-4',
  type: PropertyType.P19,
  entity_id: 'Q300',
  entity_name: 'Capital City',
  statement_id: null,
  sources: [],
}

const citizenship: Property = {
  id: 'prop-5',
  type: PropertyType.P27,
  entity_id: 'Q400',
  entity_name: 'Testland',
  statement_id: null,
  sources: [],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PropertiesEvaluation', () => {
  it('renders section headings for date and entity properties', () => {
    render(
      <PropertiesEvaluation
        properties={[birthDate, position, birthplace, citizenship]}
        onAction={mockOnAction}
        onViewSource={mockOnViewSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.getByText('Properties')).toBeInTheDocument()
    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText('Birthplaces')).toBeInTheDocument()
    expect(screen.getByText('Citizenships')).toBeInTheDocument()
  })

  it('groups birth and death dates under Properties section', () => {
    render(
      <PropertiesEvaluation
        properties={[birthDate, deathDate]}
        onAction={mockOnAction}
        onViewSource={mockOnViewSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    // Both should be under "Properties" heading
    expect(screen.getByText('Properties')).toBeInTheDocument()
    // Should not show position/birthplace sections
    expect(screen.queryByText('Political Positions')).not.toBeInTheDocument()
  })

  it('shows add buttons when onAddProperty is provided', () => {
    render(
      <PropertiesEvaluation
        properties={[birthDate]}
        onAction={mockOnAction}
        onViewSource={mockOnViewSource}
        onHover={mockOnHover}
        activeSourceId={null}
        onAddProperty={mockOnAddProperty}
      />,
    )

    expect(screen.getByText('+ Add Date')).toBeInTheDocument()
  })

  it('hides add buttons when onAddProperty is not provided', () => {
    render(
      <PropertiesEvaluation
        properties={[birthDate]}
        onAction={mockOnAction}
        onViewSource={mockOnViewSource}
        onHover={mockOnHover}
        activeSourceId={null}
      />,
    )

    expect(screen.queryByText('+ Add Date')).not.toBeInTheDocument()
  })

  it('shows empty sections when showEmptySections is true', () => {
    render(
      <PropertiesEvaluation
        properties={[birthDate]}
        onAction={mockOnAction}
        onViewSource={mockOnViewSource}
        onHover={mockOnHover}
        activeSourceId={null}
        onAddProperty={mockOnAddProperty}
        showEmptySections
      />,
    )

    // Empty sections should still appear
    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText('+ Add Position')).toBeInTheDocument()
  })

  it('opens add form when add button is clicked', () => {
    render(
      <PropertiesEvaluation
        properties={[birthDate]}
        onAction={mockOnAction}
        onViewSource={mockOnViewSource}
        onHover={mockOnHover}
        activeSourceId={null}
        onAddProperty={mockOnAddProperty}
      />,
    )

    fireEvent.click(screen.getByText('+ Add Date'))

    // The add button should be replaced by the form
    expect(screen.queryByText('+ Add Date')).not.toBeInTheDocument()
  })
})
