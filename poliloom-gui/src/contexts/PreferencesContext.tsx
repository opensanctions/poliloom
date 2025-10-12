'use client'

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import {
  PreferenceResponse,
  PreferenceType,
  LanguageResponse,
  CountryResponse,
  WikidataEntity,
} from '@/types'

interface PreferencesContextType {
  preferences: PreferenceResponse[]
  languages: LanguageResponse[]
  countries: CountryResponse[]
  loading: boolean
  loadingLanguages: boolean
  loadingCountries: boolean
  error: string | null
  initialized: boolean
  updatePreferences: (type: PreferenceType, items: WikidataEntity[]) => Promise<void>
  refetch: () => void
}

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined)

const STORAGE_KEY = 'poliloom_preferences'

// Helper function to detect browser language and match with available languages
const detectBrowserLanguage = (availableLanguages: LanguageResponse[]): WikidataEntity[] => {
  try {
    // Get browser language codes (e.g., 'en-US', 'es', 'de-DE')
    const browserLanguages = navigator.languages || [navigator.language]

    // Extract ISO 639-1 language codes (e.g., 'en' from 'en-US')
    const iso639Codes = browserLanguages.map((lang) => lang.split('-')[0].toLowerCase())

    // Find matching languages by ISO 639-1 or ISO 639-3 codes
    const matchedLanguages: WikidataEntity[] = []

    for (const browserLang of iso639Codes) {
      const match = availableLanguages.find(
        (lang) =>
          lang.iso1_code?.toLowerCase() === browserLang ||
          lang.iso3_code?.toLowerCase() === browserLang,
      )

      if (match && !matchedLanguages.some((l) => l.wikidata_id === match.wikidata_id)) {
        matchedLanguages.push({
          wikidata_id: match.wikidata_id,
          name: match.name,
        })
      }
    }

    return matchedLanguages
  } catch (error) {
    console.warn('Failed to detect browser language:', error)
    return []
  }
}

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const [preferences, setPreferences] = useState<PreferenceResponse[]>([])
  const [languages, setLanguages] = useState<LanguageResponse[]>([])
  const [countries, setCountries] = useState<CountryResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingLanguages, setLoadingLanguages] = useState(true)
  const [loadingCountries, setLoadingCountries] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [initialized, setInitialized] = useState(false)

  // Helper function to compare preference arrays
  const preferencesEqual = (a: PreferenceResponse[], b: PreferenceResponse[]) => {
    if (a.length !== b.length) return false
    const sortedA = [...a].sort((x, y) => x.wikidata_id.localeCompare(y.wikidata_id))
    const sortedB = [...b].sort((x, y) => x.wikidata_id.localeCompare(y.wikidata_id))
    return sortedA.every(
      (val, i) =>
        val.wikidata_id === sortedB[i].wikidata_id &&
        val.preference_type === sortedB[i].preference_type,
    )
  }

  // Fetch available languages
  useEffect(() => {
    const fetchLanguages = async () => {
      try {
        const response = await fetch('/api/languages?limit=1000')
        if (!response.ok) {
          throw new Error(`Failed to fetch languages: ${response.statusText}`)
        }
        const data: LanguageResponse[] = await response.json()
        setLanguages(data)
      } catch (error) {
        console.warn('Failed to fetch languages:', error)
      } finally {
        setLoadingLanguages(false)
      }
    }

    fetchLanguages()
  }, [])

  // Fetch available countries
  useEffect(() => {
    const fetchCountries = async () => {
      try {
        const response = await fetch('/api/countries?limit=1000')
        if (!response.ok) {
          throw new Error(`Failed to fetch countries: ${response.statusText}`)
        }
        const data: CountryResponse[] = await response.json()
        setCountries(data)
      } catch (error) {
        console.warn('Failed to fetch countries:', error)
      } finally {
        setLoadingCountries(false)
      }
    }

    fetchCountries()
  }, [])

  // Load preferences from localStorage on mount
  useEffect(() => {
    const loadFromStorage = () => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
          const prefs = JSON.parse(stored)
          setPreferences(prefs)
        }
      } catch (error) {
        console.warn('Failed to load preferences from localStorage:', error)
      } finally {
        setInitialized(true)
      }
    }

    loadFromStorage()
  }, [])

  // Save preferences to localStorage
  const saveToStorage = (prefs: PreferenceResponse[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
    } catch (error) {
      console.warn('Failed to save preferences to localStorage:', error)
    }
  }

  // Update preferences on server and locally
  const updatePreferences = useCallback(
    async (preferenceType: PreferenceType, items: WikidataEntity[]) => {
      setError(null)

      const wikidata_ids = items.map((item) => item.wikidata_id)

      const response = await fetch(`/api/preferences/${preferenceType}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ wikidata_ids }),
      })

      if (!response.ok) {
        throw new Error(`Failed to update preferences: ${response.statusText}`)
      }

      // Update local state immediately
      const updated = [
        ...preferences.filter((p) => p.preference_type !== preferenceType),
        ...items.map((item) => ({
          wikidata_id: item.wikidata_id,
          name: item.name,
          preference_type: preferenceType,
        })),
      ]
      setPreferences(updated)
      saveToStorage(updated)
    },
    [preferences],
  )

  // Fetch preferences from server
  const fetchPreferences = useCallback(async () => {
    if (status !== 'authenticated') return

    // Wait for languages to be loaded before fetching preferences
    // This is necessary for browser language detection to work properly
    if (loadingLanguages) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/preferences')
      if (!response.ok) {
        throw new Error(`Failed to fetch preferences: ${response.statusText}`)
      }

      const data: PreferenceResponse[] = await response.json()

      const hasNoStoredPreferences = localStorage.getItem(STORAGE_KEY) === null
      const hasNoLanguagePreferences = !data.some(
        (p) => p.preference_type === PreferenceType.LANGUAGE,
      )

      if (hasNoStoredPreferences && hasNoLanguagePreferences) {
        const detectedLanguages = detectBrowserLanguage(languages)
        if (detectedLanguages.length > 0) {
          await updatePreferences(PreferenceType.LANGUAGE, detectedLanguages)
          return
        }
      }

      setPreferences((prev) => {
        if (preferencesEqual(prev, data)) return prev
        return data
      })

      saveToStorage(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch preferences')
    } finally {
      setLoading(false)
    }
  }, [status, updatePreferences, languages, loadingLanguages])

  // Fetch preferences when authenticated
  useEffect(() => {
    if (status === 'authenticated') {
      fetchPreferences()
    }
  }, [status, fetchPreferences])

  const value: PreferencesContextType = {
    preferences,
    languages,
    countries,
    loading,
    loadingLanguages,
    loadingCountries,
    error,
    initialized,
    updatePreferences,
    refetch: fetchPreferences,
  }

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
}

export function usePreferencesContext() {
  const context = useContext(PreferencesContext)
  if (context === undefined) {
    throw new Error('usePreferencesContext must be used within a PreferencesProvider')
  }
  return context
}
