'use client'

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useSyncExternalStore,
} from 'react'
import {
  PreferenceResponse,
  PreferenceType,
  LanguageResponse,
  CountryResponse,
  WikidataEntity,
} from '@/types'

interface UserPreferencesContextType {
  filters: PreferenceResponse[]
  languages: LanguageResponse[]
  countries: CountryResponse[]
  loadingLanguages: boolean
  loadingCountries: boolean
  initialized: boolean
  updateFilters: (type: PreferenceType, items: WikidataEntity[]) => void
  isAdvancedMode: boolean
  setAdvancedMode: (enabled: boolean) => void
}

export const UserPreferencesContext = createContext<UserPreferencesContextType | undefined>(
  undefined,
)

const FILTERS_STORAGE_KEY = 'poliloom_evaluation_filters'
const ADVANCED_MODE_KEY = 'poliloom_advanced_mode'

// Advanced mode uses useSyncExternalStore for SSR safety
function getAdvancedModeSnapshot(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(ADVANCED_MODE_KEY) === 'true'
}

function getAdvancedModeServerSnapshot(): boolean {
  return false
}

function subscribeToAdvancedMode(callback: () => void): () => void {
  window.addEventListener('storage', callback)
  return () => window.removeEventListener('storage', callback)
}

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
          lang.iso_639_1?.toLowerCase() === browserLang ||
          lang.iso_639_3?.toLowerCase() === browserLang,
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

export function UserPreferencesProvider({ children }: { children: React.ReactNode }) {
  const [filters, setFilters] = useState<PreferenceResponse[]>([])
  const [languages, setLanguages] = useState<LanguageResponse[]>([])
  const [countries, setCountries] = useState<CountryResponse[]>([])
  const [loadingLanguages, setLoadingLanguages] = useState(true)
  const [loadingCountries, setLoadingCountries] = useState(true)
  const [initialized, setInitialized] = useState(false)

  // Advanced mode state
  const isAdvancedMode = useSyncExternalStore(
    subscribeToAdvancedMode,
    getAdvancedModeSnapshot,
    getAdvancedModeServerSnapshot,
  )
  const [, forceUpdate] = useState(0)

  const setAdvancedMode = useCallback((enabled: boolean) => {
    if (enabled) {
      localStorage.setItem(ADVANCED_MODE_KEY, 'true')
    } else {
      localStorage.removeItem(ADVANCED_MODE_KEY)
    }
    forceUpdate((n) => n + 1)
  }, [])

  // Fetch available languages
  useEffect(() => {
    const fetchLanguages = async () => {
      try {
        const response = await fetch('/api/languages')
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
        const response = await fetch('/api/countries')
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

  // Save filters to localStorage
  const saveToStorage = (filters: PreferenceResponse[]) => {
    try {
      localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(filters))
    } catch (error) {
      console.warn('Failed to save evaluation filters to localStorage:', error)
    }
  }

  // Update filters locally only
  const updateFilters = useCallback((preferenceType: PreferenceType, items: WikidataEntity[]) => {
    setFilters((prevFilters) => {
      // Update local state
      const updated = [
        ...prevFilters.filter((p) => p.preference_type !== preferenceType),
        ...items.map((item) => ({
          wikidata_id: item.wikidata_id,
          name: item.name,
          preference_type: preferenceType,
        })),
      ]
      saveToStorage(updated)
      return updated
    })
  }, [])

  // Load filters from localStorage on mount
  useEffect(() => {
    const loadFromStorage = () => {
      try {
        const stored = localStorage.getItem(FILTERS_STORAGE_KEY)
        if (stored) {
          const filters = JSON.parse(stored)
          setFilters(filters)
        }
      } catch (error) {
        console.warn('Failed to load evaluation filters from localStorage:', error)
      } finally {
        setInitialized(true)
      }
    }

    loadFromStorage()
  }, [])

  // Auto-detect browser language on first visit
  useEffect(() => {
    if (!initialized || loadingLanguages || languages.length === 0) return

    const hasLanguageFilter = filters.some((p) => p.preference_type === PreferenceType.LANGUAGE)

    if (!hasLanguageFilter) {
      const detectedLanguages = detectBrowserLanguage(languages)
      if (detectedLanguages.length > 0) {
        updateFilters(PreferenceType.LANGUAGE, detectedLanguages)
      }
    }
  }, [initialized, loadingLanguages, languages, filters, updateFilters])

  const value: UserPreferencesContextType = {
    filters,
    languages,
    countries,
    loadingLanguages,
    loadingCountries,
    initialized,
    updateFilters,
    isAdvancedMode,
    setAdvancedMode,
  }

  return <UserPreferencesContext.Provider value={value}>{children}</UserPreferencesContext.Provider>
}

export function useUserPreferences() {
  const context = useContext(UserPreferencesContext)
  if (context === undefined) {
    throw new Error('useUserPreferences must be used within a UserPreferencesProvider')
  }
  return context
}

// Backwards compatibility alias
export const useEvaluationFilters = useUserPreferences
export const EvaluationFiltersProvider = UserPreferencesProvider
