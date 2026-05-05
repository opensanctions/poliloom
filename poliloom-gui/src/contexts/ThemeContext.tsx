'use client'

import React, { createContext, useContext, useEffect, useCallback } from 'react'
import { readThemeCookie, writeThemeCookie } from '@/lib/cookies'
import type { Theme } from '@/lib/cookies'

interface ThemeContextType {
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

function applyThemeToDocument(theme: Theme) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.remove('light', 'dark')
  root.classList.add(theme)
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const setTheme = useCallback((newTheme: Theme) => {
    writeThemeCookie(newTheme)
    applyThemeToDocument(newTheme)
  }, [])

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      if (readThemeCookie() === null) {
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
