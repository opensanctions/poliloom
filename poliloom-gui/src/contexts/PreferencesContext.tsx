'use client'

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
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
  loadingLanguages: boolean
  loadingCountries: boolean
  initialized: boolean
  updatePreferences: (type: PreferenceType, items: WikidataEntity[]) => void
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
  const [preferences, setPreferences] = useState<PreferenceResponse[]>([])
  const [languages, setLanguages] = useState<LanguageResponse[]>([])
  const [countries, setCountries] = useState<CountryResponse[]>([])
  const [loadingLanguages, setLoadingLanguages] = useState(true)
  const [loadingCountries, setLoadingCountries] = useState(true)
  const [initialized, setInitialized] = useState(false)

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

  // Save preferences to localStorage
  const saveToStorage = (prefs: PreferenceResponse[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
    } catch (error) {
      console.warn('Failed to save preferences to localStorage:', error)
    }
  }

  // Update preferences locally only
  const updatePreferences = useCallback(
    (preferenceType: PreferenceType, items: WikidataEntity[]) => {
      setPreferences((prevPreferences) => {
        // Update local state
        const updated = [
          ...prevPreferences.filter((p) => p.preference_type !== preferenceType),
          ...items.map((item) => ({
            wikidata_id: item.wikidata_id,
            name: item.name,
            preference_type: preferenceType,
          })),
        ]
        saveToStorage(updated)
        return updated
      })
    },
    [],
  )

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

  // Auto-detect browser language on first visit
  useEffect(() => {
    if (!initialized || loadingLanguages || languages.length === 0) return

    const hasLanguagePreference = preferences.some(
      (p) => p.preference_type === PreferenceType.LANGUAGE,
    )

    if (!hasLanguagePreference) {
      const detectedLanguages = detectBrowserLanguage(languages)
      if (detectedLanguages.length > 0) {
        updatePreferences(PreferenceType.LANGUAGE, detectedLanguages)
      }
    }
  }, [initialized, loadingLanguages, languages, preferences, updatePreferences])

  const value: PreferencesContextType = {
    preferences,
    languages,
    countries,
    loadingLanguages,
    loadingCountries,
    initialized,
    updatePreferences,
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
