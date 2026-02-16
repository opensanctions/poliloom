'use client'

import React, { createContext, useContext, useEffect, useCallback } from 'react'

interface ThemeContextType {
  setTheme: (theme: 'light' | 'dark') => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const THEME_COOKIE_NAME = 'poliloom_theme'

function applyThemeToDocument(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.remove('light', 'dark')
  root.classList.add(theme)
}

function setThemeCookie(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  const maxAge = 365 * 24 * 60 * 60 // 1 year
  document.cookie = `${THEME_COOKIE_NAME}=${theme}; path=/; max-age=${maxAge}; SameSite=Lax`
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const setTheme = useCallback((newTheme: 'light' | 'dark') => {
    setThemeCookie(newTheme)
    applyThemeToDocument(newTheme)
  }, [])

  // Follow system preference when no cookie is set
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      if (!document.cookie.includes(THEME_COOKIE_NAME)) {
        applyThemeToDocument(e.matches ? 'dark' : 'light')
      }
    }
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  return <ThemeContext.Provider value={{ setTheme }}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
