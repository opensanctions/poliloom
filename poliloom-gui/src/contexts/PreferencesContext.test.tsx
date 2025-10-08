import { render, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { PreferencesProvider, usePreferencesContext } from './PreferencesContext'
import { useSession } from 'next-auth/react'
import { PreferenceType } from '@/types'

// Mock next-auth/react
vi.mock('next-auth/react')

// Test component to access context
function TestComponent() {
  const { preferences, loading, initialized } = usePreferencesContext()
  return (
    <div>
      <div data-testid="preferences">{JSON.stringify(preferences)}</div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="initialized">{String(initialized)}</div>
    </div>
  )
}

describe('PreferencesContext', () => {
  let localStorageMock: Record<string, string>
  let fetchMock: ReturnType<typeof vi.fn>

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
    fetchMock = vi.fn()
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('detects browser language on first load when no localStorage and no server preferences', async () => {
    // Mock authenticated session
    vi.mocked(useSession).mockReturnValue({
      data: { user: { name: 'Test' }, accessToken: 'token', expires: '2099-12-31T23:59:59.999Z' },
      status: 'authenticated',
      update: vi.fn(),
    })

    // Mock API responses
    fetchMock
      // First call: fetch preferences (empty)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      })
      // Second call: fetch available languages for detection
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { wikidata_id: 'Q1860', name: 'English', iso1_code: 'en', iso3_code: 'eng' },
        ],
      })
      // Third call: update preferences with detected language
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })
      // Fourth call: refetch preferences after update
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { wikidata_id: 'Q1860', name: 'English', preference_type: PreferenceType.LANGUAGE },
        ],
      })

    render(
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/preferences')
    })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/languages')
    })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/preferences/language',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ wikidata_ids: ['Q1860'] }),
        }),
      )
    })

    // Verify localStorage was never checked for preferences (it should check once at mount and find nothing)
    expect(global.localStorage.getItem).toHaveBeenCalledWith('poliloom_preferences')
  })

  it('does NOT detect browser language when localStorage already has preferences', async () => {
    // Pre-populate localStorage
    localStorageMock['poliloom_preferences'] = JSON.stringify([
      { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
    ])

    // Mock authenticated session
    vi.mocked(useSession).mockReturnValue({
      data: { user: { name: 'Test' }, accessToken: 'token', expires: '2099-12-31T23:59:59.999Z' },
      status: 'authenticated',
      update: vi.fn(),
    })

    // Mock API responses
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    })

    render(
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/preferences')
    })

    // Should NOT call /api/languages (browser detection should not run)
    await waitFor(() => {
      expect(fetchMock).not.toHaveBeenCalledWith('/api/languages')
    })

    // Should NOT call preferences update
    expect(fetchMock).not.toHaveBeenCalledWith('/api/preferences/language', expect.anything())
  })

  it('does NOT detect browser language when server already has preferences', async () => {
    // Mock authenticated session
    vi.mocked(useSession).mockReturnValue({
      data: { user: { name: 'Test' }, accessToken: 'token', expires: '2099-12-31T23:59:59.999Z' },
      status: 'authenticated',
      update: vi.fn(),
    })

    // Mock API responses with existing server preferences
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
      ],
    })

    render(
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/preferences')
    })

    // Should NOT call /api/languages (browser detection should not run)
    await waitFor(() => {
      expect(fetchMock).not.toHaveBeenCalledWith('/api/languages')
    })

    // Should NOT call preferences update
    expect(fetchMock).not.toHaveBeenCalledWith('/api/preferences/language', expect.anything())
  })

  it('does NOT detect browser language when both localStorage and server have preferences', async () => {
    // Pre-populate localStorage
    localStorageMock['poliloom_preferences'] = JSON.stringify([
      { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
    ])

    // Mock authenticated session
    vi.mocked(useSession).mockReturnValue({
      data: { user: { name: 'Test' }, accessToken: 'token', expires: '2099-12-31T23:59:59.999Z' },
      status: 'authenticated',
      update: vi.fn(),
    })

    // Mock API responses with existing server preferences
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { wikidata_id: 'Q150', name: 'French', preference_type: PreferenceType.LANGUAGE },
      ],
    })

    render(
      <PreferencesProvider>
        <TestComponent />
      </PreferencesProvider>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/preferences')
    })

    // Should NOT call /api/languages (browser detection should not run)
    await waitFor(() => {
      expect(fetchMock).not.toHaveBeenCalledWith('/api/languages')
    })

    // Should NOT call preferences update
    expect(fetchMock).not.toHaveBeenCalledWith('/api/preferences/language', expect.anything())
  })
})
