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

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Berlin')).toBeInTheDocument()
      expect(screen.getByText('Los Angeles')).toBeInTheDocument()
    })

    expect(global.fetch).toHaveBeenCalledWith('/api/locations/search?q=Ber')
  })

  it('shows description and QID in results', async () => {
    mockFetchSuccess()

    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.getByText('Q64')).toBeInTheDocument()
    })
  })

  it('calls onSelect when a result is clicked', async () => {
    mockFetchSuccess()

    render(<EntitySearch searchEndpoint="/api/locations/search" onSelect={mockOnSelect} />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ber' } })

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

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ber' } })

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

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Ber' } })

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    })
  })
})
