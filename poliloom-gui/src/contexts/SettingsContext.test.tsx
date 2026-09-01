import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { SettingsProvider, useSettings } from './SettingsContext'
import type { UserSettings } from '@/types'

const SETTINGS: UserSettings = {
  advanced_mode: false,
  basic_tutorial_completed: false,
  advanced_tutorial_completed: false,
}

function mockPatchOk(returned: UserSettings) {
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: true,
    json: async () => returned,
  } as Response)
}

function mockPatchFail() {
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: false,
    status: 500,
    json: async () => ({}),
  } as Response)
}

describe('SettingsContext', () => {
  it('exposes the seeded settings without fetching', () => {
    const { result } = renderHook(() => useSettings(), {
      wrapper: ({ children }) => (
        <SettingsProvider initialSettings={SETTINGS}>{children}</SettingsProvider>
      ),
    })
    expect(result.current.settings).toEqual(SETTINGS)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('exposes null when seeded with null (unauthenticated)', () => {
    const { result } = renderHook(() => useSettings(), {
      wrapper: ({ children }) => (
        <SettingsProvider initialSettings={null}>{children}</SettingsProvider>
      ),
    })
    expect(result.current.settings).toBeNull()
  })

  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useSettings())).toThrow(
      'useSettings must be used within a SettingsProvider',
    )
  })

  describe('patch', () => {
    it('optimistically merges and PATCHes the flat body', async () => {
      const { result } = renderHook(() => useSettings(), {
        wrapper: ({ children }) => (
          <SettingsProvider initialSettings={SETTINGS}>{children}</SettingsProvider>
        ),
      })

      mockPatchOk({ ...SETTINGS, advanced_mode: true })
      await act(async () => {
        await result.current.patch({ advanced_mode: true })
      })

      expect(result.current.settings?.advanced_mode).toBe(true)

      const [url, init] = vi.mocked(fetch).mock.calls[0]
      expect(url).toBe('/api/settings')
      expect(JSON.parse((init as RequestInit).body as string)).toEqual({
        advanced_mode: true,
      })
    })

    it('is a no-op when seeded with null (unauthenticated)', async () => {
      const { result } = renderHook(() => useSettings(), {
        wrapper: ({ children }) => (
          <SettingsProvider initialSettings={null}>{children}</SettingsProvider>
        ),
      })

      await act(async () => {
        await result.current.patch({ advanced_mode: true })
      })

      expect(result.current.settings).toBeNull()
      expect(fetch).not.toHaveBeenCalled()
    })

    it('keeps optimistic state on PATCH failure', async () => {
      vi.spyOn(console, 'warn').mockImplementation(() => {})

      const { result } = renderHook(() => useSettings(), {
        wrapper: ({ children }) => (
          <SettingsProvider initialSettings={SETTINGS}>{children}</SettingsProvider>
        ),
      })

      mockPatchFail()
      await act(async () => {
        await result.current.patch({ advanced_mode: true })
      })

      // Optimistic update stays in place; user-facing error handling is TODO.
      expect(result.current.settings).toEqual({ ...SETTINGS, advanced_mode: true })
    })

    it('replaces state with server response on success', async () => {
      const { result } = renderHook(() => useSettings(), {
        wrapper: ({ children }) => (
          <SettingsProvider initialSettings={SETTINGS}>{children}</SettingsProvider>
        ),
      })

      // Server normalizes — say it returns advanced_mode true even though we asked false.
      mockPatchOk({ ...SETTINGS, advanced_mode: true })
      await act(async () => {
        await result.current.patch({ advanced_mode: false })
      })

      expect(result.current.settings).toEqual({
        ...SETTINGS,
        advanced_mode: true,
      })
    })

    it('sends a request every time patch is called', async () => {
      const { result } = renderHook(() => useSettings(), {
        wrapper: ({ children }) => (
          <SettingsProvider initialSettings={SETTINGS}>{children}</SettingsProvider>
        ),
      })

      mockPatchOk({ ...SETTINGS, advanced_mode: true })
      await act(async () => {
        await result.current.patch({ advanced_mode: true })
      })

      mockPatchOk({ ...SETTINGS, advanced_mode: false })
      await act(async () => {
        await result.current.patch({ advanced_mode: false })
      })

      expect(fetch).toHaveBeenCalledTimes(2)
      expect(result.current.settings?.advanced_mode).toBe(false)
    })
  })
})
