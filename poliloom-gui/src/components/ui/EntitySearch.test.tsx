import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EntitySearch } from './EntitySearch'

const mockResults = [
  { wikidata_id: 'Q64', name: 'Berlin', description: 'capital of Germany' },
  { wikidata_id: 'Q65', name: 'Los Angeles', description: 'city in California' },
]

function mockFetchSuccess(results = mockResults) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: true,
    json: async () => results,
  })
}

function mockFetchFailure() {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    ok: false,
  })
}

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

describe('EntitySearch', () => {
  const mockOnSelect = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders search input with placeholder', () => {
    render(
      <EntitySearch
        searchEndpoint="/api/locations/search"
        onSelect={mockOnSelect}
        placeholder="Search for a location..."
      />,
    )

    expect(screen.getByPlaceholderText('Search for a location...')).toBeInTheDocument()
  })

  it('shows search results when typing', async () => {
    mockFetchSuccess()

    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
      expect(screen.getByText('Los Angeles')).toBeInTheDocument()
    })

    expect(global.fetch).toHaveBeenCalledWith('/api/locations/search?q=Ber')
  })

  it('shows description and QID in results', async () => {
    mockFetchSuccess()

    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Q64')).toBeInTheDocument()
    })
  })

  it('calls onSelect when a result is clicked', async () => {
    mockFetchSuccess()

    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Berlin'))

    expect(mockOnSelect).toHaveBeenCalledWith({ wikidata_id: 'Q64', name: 'Berlin' })
  })

  it('closes dropdown on click outside', async () => {
    mockFetchSuccess()

    render(
      <div>
        <div data-testid="outside">Outside</div>
        <EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />
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
    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('handles fetch errors gracefully', async () => {
    mockFetchFailure()

    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    })
  })

  describe('keyboard navigation', () => {
    async function openDropdown() {
      mockFetchSuccess()
      render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)
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
      mockFetchSuccess()

      render(
        <EntitySearch
          searchEndpoint="/api/locations/search"
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
