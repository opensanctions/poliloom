import { render, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { PreferencesProvider, usePreferencesContext } from './PreferencesContext'
import { PreferenceType } from '@/types'

// Test component to access context
function TestComponent() {
  const { preferences, initialized } = usePreferencesContext()
  return (
    <div>
      <div data-testid="preferences">{JSON.stringify(preferences)}</div>
      <div data-testid="initialized">{String(initialized)}</div>
    </div>
  )
}

describe('PreferencesContext', () => {
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

  it('detects browser language on first load when no localStorage preferences exist', async () => {
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
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
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
        'poliloom_preferences',
        expect.stringContaining('Q1860'),
      )
    })

    // Verify localStorage was checked for preferences
    expect(global.localStorage.getItem).toHaveBeenCalledWith('poliloom_preferences')
  })

  it('does NOT detect browser language when localStorage already has preferences', async () => {
    // Pre-populate localStorage
    localStorageMock['poliloom_preferences'] = JSON.stringify([
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
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/languages?limit=1000')
    })

    // Wait for initialization
    await waitFor(() => {
      const testElement = document.querySelector('[data-testid="initialized"]')
      expect(testElement?.textContent).toBe('true')
    })

    // Should NOT update preferences (browser detection should not run because localStorage has preferences)
    // The setItem call count should remain at 0 since we're not updating
    const setItemCalls = vi.mocked(global.localStorage.setItem).mock.calls
    const preferenceUpdateCalls = setItemCalls.filter((call) => call[0] === 'poliloom_preferences')
    expect(preferenceUpdateCalls.length).toBe(0)
  })

  it('loads preferences from localStorage on mount', async () => {
    // Pre-populate localStorage with preferences
    const existingPreferences = [
      { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
      { wikidata_id: 'Q142', name: 'France', preference_type: PreferenceType.COUNTRY },
    ]
    localStorageMock['poliloom_preferences'] = JSON.stringify(existingPreferences)

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
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(getByTestId('initialized').textContent).toBe('true')
    })

    await waitFor(() => {
      const preferencesText = getByTestId('preferences').textContent || ''
      const preferences = JSON.parse(preferencesText)
      expect(preferences).toEqual(existingPreferences)
    })
  })

  it('persists preference updates to localStorage', async () => {
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
      const { updatePreferences, initialized } = usePreferencesContext()

      return (
        <div>
          <div data-testid="initialized">{String(initialized)}</div>
          <button
            onClick={() =>
              updatePreferences(PreferenceType.LANGUAGE, [
                { wikidata_id: 'Q1860', name: 'English' },
              ])
            }
          >
            Update
          </button>
        </div>
      )
    }

    const { getByText, getByTestId } = render(
      <PreferencesProvider>
        <TestComponentWithUpdate />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(getByTestId('initialized').textContent).toBe('true')
    })

    // Click update button
    getByText('Update').click()

    // Wait for localStorage to be updated
    await waitFor(() => {
      expect(global.localStorage.setItem).toHaveBeenCalledWith(
        'poliloom_preferences',
        expect.stringContaining('Q1860'),
      )
    })
  })
})
