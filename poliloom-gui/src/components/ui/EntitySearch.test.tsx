import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EntitySearch } from './EntitySearch'
import { SearchFn } from '@/types'

const mockResults = [
  { wikidata_id: 'Q64', name: 'Berlin', description: 'capital of Germany' },
  { wikidata_id: 'Q65', name: 'Los Angeles', description: 'city in California' },
]

function createMockSearch(results = mockResults): SearchFn {
  return vi.fn().mockResolvedValue(results)
}

function createFailingSearch(): SearchFn {
  return vi.fn().mockRejectedValue(new Error('Search failed'))
}

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

describe('EntitySearch', () => {
  const mockOnSelect = vi.fn()

  it('renders search input with placeholder', () => {
    render(
      <EntitySearch
        onSearch={createMockSearch()}
        onSelect={mockOnSelect}
        placeholder="Search for a location..."
      />,
    )

    expect(screen.getByPlaceholderText('Search for a location...')).toBeInTheDocument()
  })

  it('shows search results when typing', async () => {
    const mockSearch = createMockSearch()

    render(<EntitySearch onSearch={mockSearch} onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
      expect(screen.getByText('Los Angeles')).toBeInTheDocument()
    })

    expect(mockSearch).toHaveBeenCalledWith('Ber')
  })

  it('shows description and QID in results', async () => {
    render(<EntitySearch onSearch={createMockSearch()} onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Q64')).toBeInTheDocument()
    })
  })

  it('calls onSelect when a result is clicked', async () => {
    render(<EntitySearch onSearch={createMockSearch()} onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Berlin'))

    expect(mockOnSelect).toHaveBeenCalledWith({ wikidata_id: 'Q64', name: 'Berlin' })
  })

  it('closes dropdown on click outside', async () => {
    render(
      <div>
        <div data-testid="outside">Outside</div>
        <EntitySearch onSearch={createMockSearch()} onSelect={mockOnSelect} />
      </div>,
    )

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getByTestId('outside'))

    await waitFor(() => {
      expect(screen.queryByText('Berlin')).not.toBeInTheDocument()
    })
  })

  it('does not show dropdown when query is empty', () => {
    render(<EntitySearch onSearch={createMockSearch()} onSelect={mockOnSelect} />)

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('handles search errors gracefully', async () => {
    render(<EntitySearch onSearch={createFailingSearch()} onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    })
  })

  describe('keyboard navigation', () => {
    async function openDropdown() {
      render(<EntitySearch onSearch={createMockSearch()} onSelect={mockOnSelect} />)
      const input = screen.getByRole('combobox')
      fireEvent.change(input, { target: { value: 'Ber' } })
      await waitFor(() => expect(screen.getByText('Berlin')).toBeInTheDocument())
      return input
    }

    it('highlights options with arrow keys', async () => {
      const input = await openDropdown()

      fireEvent.keyDown(input, { key: 'ArrowDown' })
      expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true')

      fireEvent.keyDown(input, { key: 'ArrowDown' })
      expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'false')
      expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
    })

    it('wraps around when navigating past the end', async () => {
      const input = await openDropdown()

      fireEvent.keyDown(input, { key: 'ArrowDown' })
      fireEvent.keyDown(input, { key: 'ArrowDown' })
      fireEvent.keyDown(input, { key: 'ArrowDown' })
      expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true')
    })

    it('navigates up from top wraps to bottom', async () => {
      const input = await openDropdown()

      fireEvent.keyDown(input, { key: 'ArrowUp' })
      expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
    })

    it('selects option on Enter', async () => {
      const input = await openDropdown()

      fireEvent.keyDown(input, { key: 'ArrowDown' })
      fireEvent.keyDown(input, { key: 'Enter' })

      expect(mockOnSelect).toHaveBeenCalledWith({ wikidata_id: 'Q64', name: 'Berlin' })
    })

    it('closes dropdown on Escape', async () => {
      const input = await openDropdown()

      fireEvent.keyDown(input, { key: 'Escape' })

      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    })

    it('navigates create option with arrow keys', async () => {
      const mockOnCreate = vi.fn()

      render(
        <EntitySearch
          onSearch={createMockSearch()}
          onSelect={mockOnSelect}
          onCreate={mockOnCreate}
        />,
      )

      const input = screen.getByRole('combobox')
      fireEvent.change(input, { target: { value: 'Ber' } })
      await waitFor(() => expect(screen.getByText('Berlin')).toBeInTheDocument())

      // First option should be the create option
      fireEvent.keyDown(input, { key: 'ArrowDown' })
      fireEvent.keyDown(input, { key: 'Enter' })

      expect(mockOnCreate).toHaveBeenCalledWith('Ber')
    })
  })
})
