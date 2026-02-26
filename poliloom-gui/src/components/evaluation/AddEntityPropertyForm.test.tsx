import { render, screen, fireEvent } from '@testing-library/react'
import { AddEntityPropertyForm } from './AddEntityPropertyForm'
import { PropertyType } from '@/types'

describe('AddEntityPropertyForm', () => {
  const mockOnAdd = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders QID and name inputs', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    expect(screen.getByPlaceholderText('QID (e.g. Q64)')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Name')).toBeInTheDocument()
  })

  it('disables Add button when fields are empty', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('disables Add button with invalid QID', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q64)'), {
      target: { value: 'invalid' },
    })
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'Berlin' } })

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('disables Add button with empty name', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q64)'), {
      target: { value: 'Q64' },
    })

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('enables Add button with valid QID and name', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q64)'), {
      target: { value: 'Q64' },
    })
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'Berlin' } })

    expect(screen.getByText('Add')).not.toBeDisabled()
  })

  it('calls onAdd with correct birthplace property', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q64)'), {
      target: { value: 'Q64' },
    })
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'Berlin' } })
    fireEvent.click(screen.getByText('Add'))

    expect(mockOnAdd).toHaveBeenCalledTimes(1)
    const property = mockOnAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P19)
    expect(property.entity_id).toBe('Q64')
    expect(property.entity_name).toBe('Berlin')
    expect(property.evaluation).toBe(true)
    expect(property.sources).toEqual([])
    expect(property.statement_id).toBeNull()
    expect(property.key).toMatch(/^new-/)
  })

  it('calls onAdd with correct citizenship property', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P27} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q64)'), {
      target: { value: 'Q183' },
    })
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'Germany' } })
    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P27)
    expect(property.entity_id).toBe('Q183')
    expect(property.entity_name).toBe('Germany')
  })

  it('trims entity name whitespace', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('QID (e.g. Q64)'), {
      target: { value: 'Q64' },
    })
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: '  Berlin  ' } })
    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.entity_name).toBe('Berlin')
  })

  it('calls onCancel when Cancel button is clicked', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.click(screen.getByText('Cancel'))

    expect(mockOnCancel).toHaveBeenCalledTimes(1)
  })
})
