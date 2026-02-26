import { render, screen, fireEvent } from '@testing-library/react'
import { AddPositionPropertyForm } from './AddPositionPropertyForm'
import { PropertyType } from '@/types'

describe('AddPositionPropertyForm', () => {
  const mockOnAdd = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders QID, name, and date inputs', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    expect(screen.getByPlaceholderText('QID (e.g. Q30185)')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Position name')).toBeInTheDocument()
    expect(screen.getByText('Start')).toBeInTheDocument()
    expect(screen.getByText('End')).toBeInTheDocument()
  })

  it('disables Add button when fields are empty', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('disables Add button with invalid QID', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q30185)'), {
      target: { value: 'invalid' },
    })
    fireEvent.change(screen.getByPlaceholderText('Position name'), {
      target: { value: 'Mayor' },
    })

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('calls onAdd with correct property without dates', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q30185)'), {
      target: { value: 'Q30185' },
    })
    fireEvent.change(screen.getByPlaceholderText('Position name'), {
      target: { value: 'Mayor' },
    })
    fireEvent.click(screen.getByText('Add'))

    expect(mockOnAdd).toHaveBeenCalledTimes(1)
    const property = mockOnAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P39)
    expect(property.entity_id).toBe('Q30185')
    expect(property.entity_name).toBe('Mayor')
    expect(property.qualifiers).toBeUndefined()
    expect(property.evaluation).toBe(true)
    expect(property.sources).toEqual([])
    expect(property.statement_id).toBeNull()
    expect(property.key).toMatch(/^new-/)
  })

  it('includes start date qualifier when provided', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q30185)'), {
      target: { value: 'Q30185' },
    })
    fireEvent.change(screen.getByPlaceholderText('Position name'), {
      target: { value: 'Mayor' },
    })

    // The start date picker has Year/Month/Day inputs — grab by label context
    const yearInputs = screen.getAllByPlaceholderText('Year')
    const monthInputs = screen.getAllByPlaceholderText('Month')
    const dayInputs = screen.getAllByPlaceholderText('Day')

    // First set is Start, second set is End
    fireEvent.change(yearInputs[0], { target: { value: '2020' } })
    fireEvent.change(monthInputs[0], { target: { value: '01' } })
    fireEvent.change(dayInputs[0], { target: { value: '15' } })

    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.qualifiers).toBeDefined()
    expect(property.qualifiers.P580).toHaveLength(1)
    expect(property.qualifiers.P580[0].datavalue.value.time).toBe('+2020-01-15T00:00:00Z')
    expect(property.qualifiers.P580[0].datavalue.value.precision).toBe(11)
    expect(property.qualifiers.P582).toBeUndefined()
  })

  it('includes both start and end date qualifiers when provided', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q30185)'), {
      target: { value: 'Q30185' },
    })
    fireEvent.change(screen.getByPlaceholderText('Position name'), {
      target: { value: 'Mayor' },
    })

    const yearInputs = screen.getAllByPlaceholderText('Year')
    const monthInputs = screen.getAllByPlaceholderText('Month')
    const dayInputs = screen.getAllByPlaceholderText('Day')

    fireEvent.change(yearInputs[0], { target: { value: '2020' } })
    fireEvent.change(monthInputs[0], { target: { value: '01' } })
    fireEvent.change(dayInputs[0], { target: { value: '15' } })

    fireEvent.change(yearInputs[1], { target: { value: '2024' } })
    fireEvent.change(monthInputs[1], { target: { value: '06' } })
    fireEvent.change(dayInputs[1], { target: { value: '30' } })

    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.qualifiers.P580[0].datavalue.value.time).toBe('+2020-01-15T00:00:00Z')
    expect(property.qualifiers.P582[0].datavalue.value.time).toBe('+2024-06-30T00:00:00Z')
  })

  it('trims entity name whitespace', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q30185)'), {
      target: { value: 'Q30185' },
    })
    fireEvent.change(screen.getByPlaceholderText('Position name'), {
      target: { value: '  Mayor of Berlin  ' },
    })
    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.entity_name).toBe('Mayor of Berlin')
  })

  it('calls onCancel when Cancel button is clicked', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.click(screen.getByText('Cancel'))

    expect(mockOnCancel).toHaveBeenCalledTimes(1)
  })
})
