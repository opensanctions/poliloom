import { render, screen, fireEvent } from '@testing-library/react'
import { AddDatePropertyForm } from './AddDatePropertyForm'
import { PropertyType } from '@/types'

describe('AddDatePropertyForm', () => {
  it('renders type selector and date inputs', () => {
    render(<AddDatePropertyForm onAdd={vi.fn()} onCancel={vi.fn()} />)

    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Year')).toBeInTheDocument()
    expect(screen.getByText('Month')).toBeInTheDocument()
    expect(screen.getByText('Day')).toBeInTheDocument()
  })

  it('disables Add button when no year is entered', () => {
    render(<AddDatePropertyForm onAdd={vi.fn()} onCancel={vi.fn()} />)

    expect(screen.getByText('+ Add')).toBeDisabled()
  })

  it('enables Add button when year is entered', () => {
    render(<AddDatePropertyForm onAdd={vi.fn()} onCancel={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '1990' } })

    expect(screen.getByText('+ Add')).not.toBeDisabled()
  })

  it('calls onAdd with correct property for day precision', () => {
    const onAdd = vi.fn()
    render(<AddDatePropertyForm onAdd={onAdd} onCancel={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '1990' } })
    // Select month "May" from the Month dropdown
    fireEvent.click(screen.getByRole('button', { name: /Month/i }))
    fireEvent.click(screen.getByRole('option', { name: 'May' }))
    // Select day "15" from the Day dropdown
    fireEvent.click(screen.getByRole('button', { name: /Day/i }))
    fireEvent.click(screen.getByRole('option', { name: '15' }))
    fireEvent.click(screen.getByText('+ Add'))

    expect(onAdd).toHaveBeenCalledTimes(1)
    const property = onAdd.mock.calls[0][0]
    expect(property.action).toBe('create')
    expect(property.type).toBe(PropertyType.P569)
    expect(property.value).toBe('+1990-05-15T00:00:00Z')
    expect(property.value_precision).toBe(11)
    expect(property.id).toMatch(/^[0-9a-f]{8}-/)
  })

  it('infers month precision when day is omitted', () => {
    const onAdd = vi.fn()
    render(<AddDatePropertyForm onAdd={onAdd} onCancel={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '1990' } })
    // Select month "May" from the Month dropdown
    fireEvent.click(screen.getByRole('button', { name: /Month/i }))
    fireEvent.click(screen.getByRole('option', { name: 'May' }))
    fireEvent.click(screen.getByText('+ Add'))

    const property = onAdd.mock.calls[0][0]
    expect(property.value).toBe('+1990-05-00T00:00:00Z')
    expect(property.value_precision).toBe(10)
  })

  it('infers year precision when month and day are omitted', () => {
    const onAdd = vi.fn()
    render(<AddDatePropertyForm onAdd={onAdd} onCancel={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '1990' } })
    fireEvent.click(screen.getByText('+ Add'))

    const property = onAdd.mock.calls[0][0]
    expect(property.value).toBe('+1990-00-00T00:00:00Z')
    expect(property.value_precision).toBe(9)
  })

  it('allows selecting Death Date type', () => {
    const onAdd = vi.fn()
    render(<AddDatePropertyForm onAdd={onAdd} onCancel={vi.fn()} />)

    // Open the Select dropdown and pick Death Date
    fireEvent.click(screen.getByRole('button', { name: /Birth Date/i }))
    fireEvent.click(screen.getByRole('option', { name: /Death Date/i }))

    fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '2020' } })
    fireEvent.click(screen.getByText('+ Add'))

    const property = onAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P570)
  })

  it('calls onCancel when Cancel button is clicked', () => {
    const onCancel = vi.fn()
    render(<AddDatePropertyForm onAdd={vi.fn()} onCancel={onCancel} />)

    fireEvent.click(screen.getByText('Cancel'))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
