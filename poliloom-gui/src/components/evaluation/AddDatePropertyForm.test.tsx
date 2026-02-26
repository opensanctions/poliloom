import { render, screen, fireEvent } from '@testing-library/react'
import { AddDatePropertyForm } from './AddDatePropertyForm'
import { PropertyType } from '@/types'

describe('AddDatePropertyForm', () => {
  const mockOnAdd = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders type selector, date input, and precision selector', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('Death Date')).toBeInTheDocument()
    expect(screen.getByText('Day')).toBeInTheDocument()
    expect(screen.getByText('Month')).toBeInTheDocument()
    expect(screen.getByText('Year')).toBeInTheDocument()
  })

  it('disables Add button when no date is entered', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('enables Add button when date is entered', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    const dateInput = screen.getByDisplayValue('')
    fireEvent.change(dateInput, { target: { value: '1990-05-15' } })

    expect(screen.getByText('Add')).not.toBeDisabled()
  })

  it('calls onAdd with correct property for day precision', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    const dateInput = screen.getByDisplayValue('')
    fireEvent.change(dateInput, { target: { value: '1990-05-15' } })
    fireEvent.click(screen.getByText('Add'))

    expect(mockOnAdd).toHaveBeenCalledTimes(1)
    const property = mockOnAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P569)
    expect(property.value).toBe('+1990-05-15T00:00:00Z')
    expect(property.value_precision).toBe(11)
    expect(property.evaluation).toBe(true)
    expect(property.sources).toEqual([])
    expect(property.statement_id).toBeNull()
    expect(property.key).toMatch(/^new-/)
  })

  it('zeroes out day for month precision', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    const dateInput = screen.getByDisplayValue('')
    fireEvent.change(dateInput, { target: { value: '1990-05-15' } })

    // Change precision to month
    const precisionSelect = screen.getByDisplayValue('Day')
    fireEvent.change(precisionSelect, { target: { value: '10' } })

    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.value).toBe('+1990-05-00T00:00:00Z')
    expect(property.value_precision).toBe(10)
  })

  it('zeroes out month and day for year precision', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    const dateInput = screen.getByDisplayValue('')
    fireEvent.change(dateInput, { target: { value: '1990-05-15' } })

    const precisionSelect = screen.getByDisplayValue('Day')
    fireEvent.change(precisionSelect, { target: { value: '9' } })

    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.value).toBe('+1990-00-00T00:00:00Z')
    expect(property.value_precision).toBe(9)
  })

  it('allows selecting Death Date type', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    const typeSelect = screen.getByDisplayValue('Birth Date')
    fireEvent.change(typeSelect, { target: { value: PropertyType.P570 } })

    const dateInput = screen.getByDisplayValue('')
    fireEvent.change(dateInput, { target: { value: '2020-01-01' } })
    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P570)
  })

  it('calls onCancel when Cancel button is clicked', () => {
    render(<AddDatePropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.click(screen.getByText('Cancel'))

    expect(mockOnCancel).toHaveBeenCalledTimes(1)
  })
})
