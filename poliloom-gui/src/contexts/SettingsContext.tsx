'use client'

import React, { createContext, useCallback, useContext, useState } from 'react'
import { UserSettings } from '@/types'

interface SettingsContextType {
  settings: UserSettings | null
  patch: (body: Partial<UserSettings>) => Promise<void>
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

export function SettingsProvider({
  initialSettings,
  children,
}: {
  initialSettings: UserSettings | null
  children: React.ReactNode
}) {
  const [settings, setSettings] = useState<UserSettings | null>(initialSettings)

  const patch = useCallback(
    async (body: Partial<UserSettings>) => {
      if (settings === null) return
      setSettings((prev) => (prev === null ? prev : { ...prev, ...body }))
      try {
        const response = await fetch('/api/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!response.ok) throw new Error(`PATCH /api/settings: ${response.status}`)
        const updated = (await response.json()) as UserSettings
        setSettings(updated)
      } catch (error) {
        console.warn('PATCH /api/settings failed:', error)
      }
    },
    [settings],
  )

  return <SettingsContext.Provider value={{ settings, patch }}>{children}</SettingsContext.Provider>
}

export function useSettings() {
  const context = useContext(SettingsContext)
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider')
  }
  return context
}
