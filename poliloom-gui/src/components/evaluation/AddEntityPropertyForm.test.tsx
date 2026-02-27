import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AddEntityPropertyForm } from './AddEntityPropertyForm'
import { PropertyType } from '@/types'

const locationResults = [
  { wikidata_id: 'Q64', name: 'Berlin', description: 'capital of Germany' },
  { wikidata_id: 'Q1022', name: 'Bern', description: 'capital of Switzerland' },
]

const countryResults = [{ wikidata_id: 'Q183', name: 'Germany', description: 'country in Europe' }]

function mockFetchSuccess(results: unknown[]) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => results,
  })
}

describe('AddEntityPropertyForm', () => {
  const mockOnAdd = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders search input for birthplace', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    expect(screen.getByPlaceholderText('Search for a location...')).toBeInTheDocument()
  })

  it('renders search input for citizenship', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P27} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    expect(screen.getByPlaceholderText('Search for a country...')).toBeInTheDocument()
  })

  it('disables Add button when no entity is selected', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    expect(screen.getByText('+ Add')).toBeDisabled()
  })

  it('searches locations endpoint for birthplace type', async () => {
    mockFetchSuccess(locationResults)

    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('Search for a location...'), {
      target: { value: 'Ber' },
    })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/locations/search?q=Ber')
    })
  })

  it('searches countries endpoint for citizenship type', async () => {
    mockFetchSuccess(countryResults)

    render(
      <AddEntityPropertyForm type={PropertyType.P27} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('Search for a country...'), {
      target: { value: 'Ger' },
    })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/countries/search?q=Ger')
    })
  })

  it('calls onAdd with correct birthplace property after search and select', async () => {
    mockFetchSuccess(locationResults)

    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('Search for a location...'), {
      target: { value: 'Ber' },
    })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Berlin'))

    expect(screen.getByText('+ Add')).not.toBeDisabled()
    fireEvent.click(screen.getByText('+ Add'))

    expect(mockOnAdd).toHaveBeenCalledTimes(1)
    const property = mockOnAdd.mock.calls[0][0]
    expect(property.action).toBe('create')
    expect(property.type).toBe(PropertyType.P19)
    expect(property.entity_id).toBe('Q64')
    expect(property.entity_name).toBe('Berlin')
    expect(property.id).toMatch(/^[0-9a-f]{8}-/)
  })

  it('calls onAdd with correct citizenship property after search and select', async () => {
    mockFetchSuccess(countryResults)

    render(
      <AddEntityPropertyForm type={PropertyType.P27} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('Search for a country...'), {
      target: { value: 'Ger' },
    })

    await waitFor(() => {
      expect(screen.getByText('Germany')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Germany'))
    fireEvent.click(screen.getByText('+ Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.type).toBe(PropertyType.P27)
    expect(property.entity_id).toBe('Q183')
    expect(property.entity_name).toBe('Germany')
  })

  it('calls onCancel when Cancel button is clicked', () => {
    render(
      <AddEntityPropertyForm type={PropertyType.P19} onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.click(screen.getByText('Cancel'))

    expect(mockOnCancel).toHaveBeenCalledTimes(1)
  })
})
