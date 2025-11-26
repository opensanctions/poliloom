import { render, waitFor, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { UserPreferencesProvider, useUserPreferences } from './UserPreferencesContext'
import { PreferenceType } from '@/types'

// Test component to access context
function TestComponent() {
  const { filters, initialized } = useUserPreferences()
  return (
    <div>
      <div data-testid="filters">{JSON.stringify(filters)}</div>
      <div data-testid="initialized">{String(initialized)}</div>
    </div>
  )
}

describe('UserPreferencesContext', () => {
  let localStorageMock: Record<string, string>
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

  beforeEach(() => {
    // Mock localStorage
    localStorageMock = {}
    global.localStorage = {
      getItem: vi.fn((key: string) => localStorageMock[key] || null),
      setItem: vi.fn((key: string, value: string) => {
        localStorageMock[key] = value
      }),
      removeItem: vi.fn((key: string) => {
        delete localStorageMock[key]
      }),
      clear: vi.fn(() => {
        localStorageMock = {}
      }),
      length: 0,
      key: vi.fn(),
    }

    // Mock navigator.languages
    Object.defineProperty(window.navigator, 'languages', {
      writable: true,
      value: ['en-US', 'en'],
    })

    // Mock fetch
    fetchMock = vi.fn<typeof fetch>()
    global.fetch = fetchMock as typeof fetch
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('detects browser language on first load when no localStorage filters exist', async () => {
    // Mock API responses
    fetchMock
      // First call: fetch available languages (on mount)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { wikidata_id: 'Q1860', name: 'English', iso1_code: 'en', iso3_code: 'eng' },
        ],
      } as Response)
      // Second call: fetch available countries (on mount)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response)

    render(
      <UserPreferencesProvider>
        <TestComponent />
      </UserPreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/languages?limit=1000')
    })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/countries?limit=1000')
    })

    // Wait for auto-detection to run
    await waitFor(() => {
      expect(global.localStorage.setItem).toHaveBeenCalledWith(
        'poliloom_evaluation_filters',
        expect.stringContaining('Q1860'),
      )
    })

    // Verify localStorage was checked for filters
    expect(global.localStorage.getItem).toHaveBeenCalledWith('poliloom_evaluation_filters')
  })

  it('does NOT detect browser language when localStorage already has filters', async () => {
    // Pre-populate localStorage
    localStorageMock['poliloom_evaluation_filters'] = JSON.stringify([
      { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
    ])

    // Mock API responses
    fetchMock
      // First call: fetch available languages (on mount)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { wikidata_id: 'Q1860', name: 'English', iso1_code: 'en', iso3_code: 'eng' },
        ],
      } as Response)
      // Second call: fetch available countries (on mount)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response)

    render(
      <UserPreferencesProvider>
        <TestComponent />
      </UserPreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/languages?limit=1000')
    })

    // Wait for initialization
    await waitFor(() => {
      const testElement = document.querySelector('[data-testid="initialized"]')
      expect(testElement?.textContent).toBe('true')
    })

    // Should NOT update filters (browser detection should not run because localStorage has filters)
    // The setItem call count should remain at 0 since we're not updating
    const setItemCalls = vi.mocked(global.localStorage.setItem).mock.calls
    const filterUpdateCalls = setItemCalls.filter(
      (call) => call[0] === 'poliloom_evaluation_filters',
    )
    expect(filterUpdateCalls.length).toBe(0)
  })

  it('loads filters from localStorage on mount', async () => {
    // Pre-populate localStorage with filters
    const existingFilters = [
      { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
      { wikidata_id: 'Q142', name: 'France', preference_type: PreferenceType.COUNTRY },
    ]
    localStorageMock['poliloom_evaluation_filters'] = JSON.stringify(existingFilters)

    // Mock API responses
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response)

    const { getByTestId } = render(
      <UserPreferencesProvider>
        <TestComponent />
      </UserPreferencesProvider>,
    )

    await waitFor(() => {
      expect(getByTestId('initialized').textContent).toBe('true')
    })

    await waitFor(() => {
      const filtersText = getByTestId('filters').textContent || ''
      const filters = JSON.parse(filtersText)
      expect(filters).toEqual(existingFilters)
    })
  })

  it('persists filter updates to localStorage', async () => {
    // Mock API responses
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { wikidata_id: 'Q1860', name: 'English', iso1_code: 'en', iso3_code: 'eng' },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response)

    function TestComponentWithUpdate() {
      const { updateFilters, initialized } = useUserPreferences()

      return (
        <div>
          <div data-testid="initialized">{String(initialized)}</div>
          <button
            onClick={() =>
              updateFilters(PreferenceType.LANGUAGE, [{ wikidata_id: 'Q1860', name: 'English' }])
            }
          >
            Update
          </button>
        </div>
      )
    }

    const { getByText, getByTestId } = render(
      <UserPreferencesProvider>
        <TestComponentWithUpdate />
      </UserPreferencesProvider>,
    )

    await waitFor(() => {
      expect(getByTestId('initialized').textContent).toBe('true')
    })

    // Click update button
    fireEvent.click(getByText('Update'))

    // Wait for localStorage to be updated
    await waitFor(() => {
      expect(global.localStorage.setItem).toHaveBeenCalledWith(
        'poliloom_evaluation_filters',
        expect.stringContaining('Q1860'),
      )
    })
  })
})
