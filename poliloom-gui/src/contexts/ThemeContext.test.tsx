import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { ThemeProvider, useTheme } from './ThemeContext'
import { readThemeCookie, writeThemeCookie } from '@/lib/cookies'

let listeners: Array<(e: MediaQueryListEvent) => void> = []

function clearCookies() {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim()
    if (name) document.cookie = `${name}=; Max-Age=0; Path=/`
  }
}

beforeEach(() => {
  clearCookies()
  document.documentElement.className = ''
  listeners = []
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener: (_: string, listener: (e: MediaQueryListEvent) => void) => {
      listeners.push(listener)
    },
    removeEventListener: vi.fn(),
  }))
})

describe('ThemeContext', () => {
  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useTheme())).toThrow(
      'useTheme must be used within a ThemeProvider',
    )
  })

  it('applies the theme and persists it when setTheme is called', () => {
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider })

    act(() => result.current.setTheme('dark'))

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(readThemeCookie()).toBe('dark')
  })

  it('follows the system preference when no theme cookie is set', () => {
    renderHook(() => useTheme(), { wrapper: ThemeProvider })

    act(() => {
      for (const listener of listeners) listener({ matches: true } as MediaQueryListEvent)
    })

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('keeps the explicit theme when the system preference changes', () => {
    writeThemeCookie('light')
    renderHook(() => useTheme(), { wrapper: ThemeProvider })

    act(() => {
      for (const listener of listeners) listener({ matches: true } as MediaQueryListEvent)
    })

    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
