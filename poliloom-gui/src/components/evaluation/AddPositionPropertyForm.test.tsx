import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AddPositionPropertyForm } from './AddPositionPropertyForm'
import { PropertyType } from '@/types'

const positionResults = [
  { wikidata_id: 'Q30185', name: 'Mayor', description: 'head of a municipality' },
  { wikidata_id: 'Q193391', name: 'Mayor of Berlin', description: 'political office' },
]

function mockFetchSuccess(results = positionResults) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => results,
  })
}

function selectDate(
  container: HTMLElement,
  dateIndex: number,
  year: string,
  month: string,
  day: string,
) {
  // Each DatePrecisionPicker has a year input and two Select dropdowns (month, day)
  // dateIndex 0 = start date, dateIndex 1 = end date
  const yearInputs = container.querySelectorAll<HTMLInputElement>('input[type="number"]')
  fireEvent.change(yearInputs[dateIndex], { target: { value: year } })

  // Find all Select dropdown buttons (aria-haspopup="listbox")
  const selectButtons = container.querySelectorAll<HTMLButtonElement>('[aria-haspopup="listbox"]')
  // Each date picker has 2 selects (month, day), so index: dateIndex*2 for month, dateIndex*2+1 for day
  const monthButton = selectButtons[dateIndex * 2]
  const dayButton = selectButtons[dateIndex * 2 + 1]

  // Select month
  fireEvent.click(monthButton)
  const monthOption = screen.getByRole('option', { name: month })
  fireEvent.click(monthOption)

  // Select day
  fireEvent.click(dayButton)
  const dayOption = screen.getByRole('option', { name: day })
  fireEvent.click(dayOption)
}

describe('AddPositionPropertyForm', () => {
  const mockOnAdd = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders search input and date pickers', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    expect(screen.getByPlaceholderText('Search for a position...')).toBeInTheDocument()
    expect(screen.getByText('Start')).toBeInTheDocument()
    expect(screen.getByText('End')).toBeInTheDocument()
  })

  it('disables Add button when no entity is selected', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    expect(screen.getByText('Add')).toBeDisabled()
  })

  it('searches positions endpoint', async () => {
    mockFetchSuccess()

    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
      target: { value: 'Mayor' },
    })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/positions/search?q=Mayor')
    })
  })

  it('calls onAdd with correct property without dates', async () => {
    mockFetchSuccess()

    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
      target: { value: 'Mayor' },
    })

    await waitFor(() => {
      expect(screen.getByText('Mayor')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Mayor'))
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

  it('includes start date qualifier when provided', async () => {
    mockFetchSuccess()

    const { container } = render(
      <AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
      target: { value: 'Mayor' },
    })

    await waitFor(() => {
      expect(screen.getByText('Mayor')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Mayor'))

    selectDate(container, 0, '2020', 'January', '15')

    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.qualifiers).toBeDefined()
    expect(property.qualifiers.P580).toHaveLength(1)
    expect(property.qualifiers.P580[0].datavalue.value.time).toBe('+2020-01-15T00:00:00Z')
    expect(property.qualifiers.P580[0].datavalue.value.precision).toBe(11)
    expect(property.qualifiers.P582).toBeUndefined()
  })

  it('includes both start and end date qualifiers when provided', async () => {
    mockFetchSuccess()

    const { container } = render(
      <AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />,
    )

    fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
      target: { value: 'Mayor' },
    })

    await waitFor(() => {
      expect(screen.getByText('Mayor')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Mayor'))

    selectDate(container, 0, '2020', 'January', '15')
    selectDate(container, 1, '2024', 'June', '30')

    fireEvent.click(screen.getByText('Add'))

    const property = mockOnAdd.mock.calls[0][0]
    expect(property.qualifiers.P580[0].datavalue.value.time).toBe('+2020-01-15T00:00:00Z')
    expect(property.qualifiers.P582[0].datavalue.value.time).toBe('+2024-06-30T00:00:00Z')
  })

  it('calls onCancel when Cancel button is clicked', () => {
    render(<AddPositionPropertyForm onAdd={mockOnAdd} onCancel={mockOnCancel} />)

    fireEvent.click(screen.getByText('Cancel'))

    expect(mockOnCancel).toHaveBeenCalledTimes(1)
  })
})
