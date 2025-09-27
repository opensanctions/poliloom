"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { PreferenceResponse, PreferenceType } from '@/types'

interface PreferencesContextType {
  languagePreferences: string[]
  countryPreferences: string[]
  loading: boolean
  error: string | null
  updateLanguagePreferences: (qids: string[]) => Promise<void>
  updateCountryPreferences: (qids: string[]) => Promise<void>
  refetch: () => void
}

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined)

const STORAGE_KEYS = {
  LANGUAGE_PREFERENCES: 'poliloom_language_preferences',
  COUNTRY_PREFERENCES: 'poliloom_country_preferences',
  PREFERENCES_TIMESTAMP: 'poliloom_preferences_timestamp'
}

const CACHE_DURATION = 5 * 60 * 1000 // 5 minutes

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const [languagePreferences, setLanguagePreferences] = useState<string[]>([])
  const [countryPreferences, setCountryPreferences] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load preferences from localStorage on mount
  useEffect(() => {
    const loadFromStorage = () => {
      try {
        const timestamp = localStorage.getItem(STORAGE_KEYS.PREFERENCES_TIMESTAMP)
        const isExpired = !timestamp || Date.now() - parseInt(timestamp) > CACHE_DURATION

        if (!isExpired) {
          const storedLanguages = localStorage.getItem(STORAGE_KEYS.LANGUAGE_PREFERENCES)
          const storedCountries = localStorage.getItem(STORAGE_KEYS.COUNTRY_PREFERENCES)

          if (storedLanguages) {
            setLanguagePreferences(JSON.parse(storedLanguages))
          }
          if (storedCountries) {
            setCountryPreferences(JSON.parse(storedCountries))
          }
        }
      } catch (error) {
        console.warn('Failed to load preferences from localStorage:', error)
      }
    }

    loadFromStorage()
  }, [])

  // Save preferences to localStorage
  const saveToStorage = (languages: string[], countries: string[]) => {
    try {
      localStorage.setItem(STORAGE_KEYS.LANGUAGE_PREFERENCES, JSON.stringify(languages))
      localStorage.setItem(STORAGE_KEYS.COUNTRY_PREFERENCES, JSON.stringify(countries))
      localStorage.setItem(STORAGE_KEYS.PREFERENCES_TIMESTAMP, Date.now().toString())
    } catch (error) {
      console.warn('Failed to save preferences to localStorage:', error)
    }
  }

  // Fetch preferences from server
  const fetchPreferences = useCallback(async () => {
    if (status !== 'authenticated') return

    setLoading(true)
    setError(null)

    const response = await fetch('/api/preferences')
    if (!response.ok) {
      throw new Error(`Failed to fetch preferences: ${response.statusText}`)
    }

    const data: PreferenceResponse[] = await response.json()

    const languages = data
      .filter(p => p.preference_type === PreferenceType.LANGUAGE)
      .map(p => p.qid)

    const countries = data
      .filter(p => p.preference_type === PreferenceType.COUNTRY)
      .map(p => p.qid)

    setLanguagePreferences(languages)
    setCountryPreferences(countries)
    saveToStorage(languages, countries)
    setLoading(false)
  }, [status])

  // Update preferences on server and locally
  const updatePreferences = async (preferenceType: PreferenceType, qids: string[]) => {
    setError(null)

    const response = await fetch(`/api/preferences/${preferenceType}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ entity_qids: qids }),
    })

    if (!response.ok) {
      throw new Error(`Failed to update preferences: ${response.statusText}`)
    }

    // Update local state immediately
    if (preferenceType === PreferenceType.LANGUAGE) {
      setLanguagePreferences(qids)
      saveToStorage(qids, countryPreferences)
    } else if (preferenceType === PreferenceType.COUNTRY) {
      setCountryPreferences(qids)
      saveToStorage(languagePreferences, qids)
    }
  }

  const updateLanguagePreferences = async (qids: string[]) => {
    await updatePreferences(PreferenceType.LANGUAGE, qids)
  }

  const updateCountryPreferences = async (qids: string[]) => {
    await updatePreferences(PreferenceType.COUNTRY, qids)
  }

  // Fetch preferences when authenticated
  useEffect(() => {
    if (status === 'authenticated') {
      fetchPreferences()
    }
  }, [status, fetchPreferences])

  const value: PreferencesContextType = {
    languagePreferences,
    countryPreferences,
    loading,
    error,
    updateLanguagePreferences,
    updateCountryPreferences,
    refetch: fetchPreferences
  }

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  )
}

export function usePreferencesContext() {
  const context = useContext(PreferencesContext)
  if (context === undefined) {
    throw new Error('usePreferencesContext must be used within a PreferencesProvider')
  }
  return context
}