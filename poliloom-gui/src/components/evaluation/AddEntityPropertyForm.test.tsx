import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AddEntityPropertyForm } from './AddEntityPropertyForm'
import { PropertyType, SearchFn } from '@/types'

const positionResults = [
  { wikidata_id: 'Q30185', name: 'Mayor', description: 'head of a municipality' },
  { wikidata_id: 'Q193391', name: 'Mayor of Berlin', description: 'political office' },
]

const locationResults = [
  { wikidata_id: 'Q64', name: 'Berlin', description: 'capital of Germany' },
  { wikidata_id: 'Q1022', name: 'Bern', description: 'capital of Switzerland' },
]

const countryResults = [{ wikidata_id: 'Q183', name: 'Germany', description: 'country in Europe' }]

function createMockSearch(results: unknown[]): SearchFn {
  return vi.fn().mockResolvedValue(results)
}

function selectDate(
  container: HTMLElement,
  dateIndex: number,
  year: string,
  month: string,
  day: string,
) {
  const yearInputs = container.querySelectorAll<HTMLInputElement>('input[type="number"]')
  fireEvent.change(yearInputs[dateIndex], { target: { value: year } })

  const selectButtons = container.querySelectorAll<HTMLButtonElement>('[aria-haspopup="listbox"]')
  const monthButton = selectButtons[dateIndex * 2]
  const dayButton = selectButtons[dateIndex * 2 + 1]

  fireEvent.click(monthButton)
  const monthOption = screen.getByRole('option', { name: month })
  fireEvent.click(monthOption)

  fireEvent.click(dayButton)
  const dayOption = screen.getByRole('option', { name: day })
  fireEvent.click(dayOption)
}

describe('AddEntityPropertyForm', () => {
  describe('position (P39)', () => {
    it('renders search input and date pickers', () => {
      render(
        <AddEntityPropertyForm
          type={PropertyType.P39}
          onAdd={vi.fn()}
          onCancel={vi.fn()}
          onSearch={vi.fn()}
        />,
      )

      expect(screen.getByPlaceholderText('Search for a position...')).toBeInTheDocument()
      expect(screen.getByText('Start')).toBeInTheDocument()
      expect(screen.getByText('End')).toBeInTheDocument()
    })

    it('searches positions', async () => {
      const mockSearch = createMockSearch(positionResults)

      render(
        <AddEntityPropertyForm
          type={PropertyType.P39}
          onAdd={vi.fn()}
          onCancel={vi.fn()}
          onSearch={mockSearch}
        />,
      )

      fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
        target: { value: 'Mayor' },
      })

      await waitFor(() => {
        expect(mockSearch).toHaveBeenCalledWith('Mayor')
      })
    })

    it('calls onAdd with correct property without dates', async () => {
      const onAdd = vi.fn()

      render(
        <AddEntityPropertyForm
          type={PropertyType.P39}
          onAdd={onAdd}
          onCancel={vi.fn()}
          onSearch={createMockSearch(positionResults)}
        />,
      )

      fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
        target: { value: 'Mayor' },
      })

      await waitFor(() => {
        expect(screen.getByText('Mayor')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Mayor'))
      fireEvent.click(screen.getByText('+ Add'))

      expect(onAdd).toHaveBeenCalledTimes(1)
      const property = onAdd.mock.calls[0][0]
      expect(property.action).toBe('create')
      expect(property.type).toBe(PropertyType.P39)
      expect(property.entity_id).toBe('Q30185')
      expect(property.entity_name).toBe('Mayor')
      expect(property.qualifiers).toBeUndefined()
      expect(property.id).toMatch(/^[0-9a-f]{8}-/)
    })

    it('includes start date qualifier when provided', async () => {
      const onAdd = vi.fn()

      const { container } = render(
        <AddEntityPropertyForm
          type={PropertyType.P39}
          onAdd={onAdd}
          onCancel={vi.fn()}
          onSearch={createMockSearch(positionResults)}
        />,
      )

      fireEvent.change(screen.getByPlaceholderText('Search for a position...'), {
        target: { value: 'Mayor' },
      })

      await waitFor(() => {
        expect(screen.getByText('Mayor')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Mayor'))
      selectDate(container, 0, '2020', 'January', '15')
      fireEvent.click(screen.getByText('+ Add'))

      const property = onAdd.mock.calls[0][0]
      expect(property.qualifiers).toBeDefined()
      expect(property.qualifiers.P580).toHaveLength(1)
      expect(property.qualifiers.P580[0].datavalue.value.time).toBe('+2020-01-15T00:00:00Z')
      expect(property.qualifiers.P580[0].datavalue.value.precision).toBe(11)
      expect(property.qualifiers.P582).toBeUndefined()
    })

    it('includes both start and end date qualifiers when provided', async () => {
      const onAdd = vi.fn()

      const { container } = render(
        <AddEntityPropertyForm
          type={PropertyType.P39}
          onAdd={onAdd}
          onCancel={vi.fn()}
          onSearch={createMockSearch(positionResults)}
        />,
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
      fireEvent.click(screen.getByText('+ Add'))

      const property = onAdd.mock.calls[0][0]
      expect(property.qualifiers.P580[0].datavalue.value.time).toBe('+2020-01-15T00:00:00Z')
      expect(property.qualifiers.P582[0].datavalue.value.time).toBe('+2024-06-30T00:00:00Z')
    })
  })

  describe('location (P19)', () => {
    it('renders search input without date pickers', () => {
      render(
        <AddEntityPropertyForm
          type={PropertyType.P19}
          onAdd={vi.fn()}
          onCancel={vi.fn()}
          onSearch={vi.fn()}
        />,
      )

      expect(screen.getByPlaceholderText('Search for a location...')).toBeInTheDocument()
      expect(screen.queryByText('Start')).not.toBeInTheDocument()
      expect(screen.queryByText('End')).not.toBeInTheDocument()
    })

    it('searches locations', async () => {
      const mockSearch = createMockSearch(locationResults)

      render(
        <AddEntityPropertyForm
          type={PropertyType.P19}
          onAdd={vi.fn()}
          onCancel={vi.fn()}
          onSearch={mockSearch}
        />,
      )

      fireEvent.change(screen.getByPlaceholderText('Search for a location...'), {
        target: { value: 'Ber' },
      })

      await waitFor(() => {
        expect(mockSearch).toHaveBeenCalledWith('Ber')
      })
    })

    it('calls onAdd with correct property', async () => {
      const onAdd = vi.fn()

      render(
        <AddEntityPropertyForm
          type={PropertyType.P19}
          onAdd={onAdd}
          onCancel={vi.fn()}
          onSearch={createMockSearch(locationResults)}
        />,
      )

      fireEvent.change(screen.getByPlaceholderText('Search for a location...'), {
        target: { value: 'Ber' },
      })

      await waitFor(() => {
        expect(screen.getByText('Berlin')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Berlin'))
      fireEvent.click(screen.getByText('+ Add'))

      expect(onAdd).toHaveBeenCalledTimes(1)
      const property = onAdd.mock.calls[0][0]
      expect(property.action).toBe('create')
      expect(property.type).toBe(PropertyType.P19)
      expect(property.entity_id).toBe('Q64')
      expect(property.entity_name).toBe('Berlin')
      expect(property.id).toMatch(/^[0-9a-f]{8}-/)
    })
  })

  describe('country (P27)', () => {
    it('renders search input without date pickers', () => {
      render(
        <AddEntityPropertyForm
          type={PropertyType.P27}
          onAdd={vi.fn()}
          onCancel={vi.fn()}
          onSearch={vi.fn()}
        />,
      )

      expect(screen.getByPlaceholderText('Search for a country...')).toBeInTheDocument()
      expect(screen.queryByText('Start')).not.toBeInTheDocument()
      expect(screen.queryByText('End')).not.toBeInTheDocument()
    })

    it('calls onAdd with correct property', async () => {
      const onAdd = vi.fn()

      render(
        <AddEntityPropertyForm
          type={PropertyType.P27}
          onAdd={onAdd}
          onCancel={vi.fn()}
          onSearch={createMockSearch(countryResults)}
        />,
      )

      fireEvent.change(screen.getByPlaceholderText('Search for a country...'), {
        target: { value: 'Ger' },
      })

      await waitFor(() => {
        expect(screen.getByText('Germany')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Germany'))
      fireEvent.click(screen.getByText('+ Add'))

      const property = onAdd.mock.calls[0][0]
      expect(property.action).toBe('create')
      expect(property.type).toBe(PropertyType.P27)
      expect(property.entity_id).toBe('Q183')
      expect(property.entity_name).toBe('Germany')
    })
  })

  it('disables Add button when no entity is selected', () => {
    render(
      <AddEntityPropertyForm
        type={PropertyType.P19}
        onAdd={vi.fn()}
        onCancel={vi.fn()}
        onSearch={vi.fn()}
      />,
    )

    expect(screen.getByText('+ Add')).toBeDisabled()
  })

  it('calls onCancel when Cancel button is clicked', () => {
    const onCancel = vi.fn()
    render(
      <AddEntityPropertyForm
        type={PropertyType.P19}
        onAdd={vi.fn()}
        onCancel={onCancel}
        onSearch={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByText('Cancel'))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
