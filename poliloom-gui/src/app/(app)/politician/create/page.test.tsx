import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, render } from '@testing-library/react'
import { mockRouterPush, mockFetch } from '@/test/test-utils'
import '@/test/highlight-mocks'
import CreatePoliticianPage from './page'
import { PropertyType } from '@/types'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: true,
  }),
}))

const mockAlert = vi.spyOn(window, 'alert').mockImplementation(() => {})
vi.spyOn(console, 'error').mockImplementation(() => {})

/** Fill name and add a birth date property so the form is submittable. */
function fillCreateForm() {
  fireEvent.change(screen.getByPlaceholderText('Politician name'), {
    target: { value: 'Jane Doe' },
  })

  // Open the add-date form (Birth Date is the default type)
  fireEvent.click(screen.getByText('+ Add Date'))

  // Enter a year and submit
  fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '1980' } })
  fireEvent.click(screen.getByText('+ Add'))
}

describe('CreatePoliticianPage', () => {
  beforeEach(() => {
    CSS.highlights.clear()
    mockRouterPush.mockClear()
    mockFetch.mockClear()
    mockAlert.mockClear()
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        wikidata_id: 'Q123456',
        message: 'Created',
        errors: [],
      }),
    })
  })

  it('renders name input and create button', () => {
    render(<CreatePoliticianPage />)

    expect(screen.getByPlaceholderText('Politician name')).toBeInTheDocument()
    expect(screen.getByText('Create Politician')).toBeInTheDocument()
  })

  it('create button is disabled when name is empty', () => {
    render(<CreatePoliticianPage />)

    expect(screen.getByText('Create Politician')).toBeDisabled()
  })

  it('create button is disabled when name is set but no properties added', () => {
    render(<CreatePoliticianPage />)

    fireEvent.change(screen.getByPlaceholderText('Politician name'), {
      target: { value: 'Jane Doe' },
    })

    expect(screen.getByText('Create Politician')).toBeDisabled()
  })

  it('create button is enabled when name and a property are provided', () => {
    render(<CreatePoliticianPage />)

    fillCreateForm()

    expect(screen.getByText('Create Politician')).not.toBeDisabled()
  })

  it('submits correct data to API and navigates on success', async () => {
    render(<CreatePoliticianPage />)

    fillCreateForm()
    fireEvent.click(screen.getByText('Create Politician'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    const body = JSON.parse(mockFetch.mock.calls[0][1].body)
    expect(body.name).toBe('Jane Doe')
    expect(body.items).toHaveLength(1)
    expect(body.items[0].action).toBe('create')
    expect(body.items[0].type).toBe(PropertyType.P569)

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q123456')
    })
  })

  it('shows alert when API returns success: false', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: false,
        message: 'Something went wrong',
        errors: ['error1'],
      }),
    })

    render(<CreatePoliticianPage />)

    fillCreateForm()
    fireEvent.click(screen.getByText('Create Politician'))

    await waitFor(() => {
      expect(mockAlert).toHaveBeenCalledWith('Error creating politician: Something went wrong')
    })
  })

  it('shows alert when API request fails', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      statusText: 'Internal Server Error',
    })

    render(<CreatePoliticianPage />)

    fillCreateForm()
    fireEvent.click(screen.getByText('Create Politician'))

    await waitFor(() => {
      expect(mockAlert).toHaveBeenCalledWith('Error creating politician. Please try again.')
    })
  })

  it('shows "Select a Source" placeholder when no archived page is selected', () => {
    render(<CreatePoliticianPage />)

    expect(screen.getByText('Select a Source')).toBeInTheDocument()
  })

  it('shows creating state while submitting', async () => {
    let resolvePromise: (value: unknown) => void
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      }),
    )

    render(<CreatePoliticianPage />)

    fillCreateForm()
    fireEvent.click(screen.getByText('Create Politician'))

    expect(screen.getByText('Creating...')).toBeInTheDocument()
    expect(screen.getByText('Creating...')).toBeDisabled()

    resolvePromise!({
      ok: true,
      json: async () => ({
        success: true,
        wikidata_id: 'Q123456',
        message: 'Created',
        errors: [],
      }),
    })

    await waitFor(() => {
      expect(screen.getByText('Create Politician')).toBeInTheDocument()
    })
  })
})
