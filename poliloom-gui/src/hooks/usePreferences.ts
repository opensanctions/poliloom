"use client"

import { useState, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { PreferenceResponse, PreferenceType, LanguageResponse } from '@/types'

interface UsePreferencesReturn {
  preferences: PreferenceResponse[]
  languagePreferences: string[]
  countryPreferences: string[]
  languageCount: number
  countryCount: number
  loading: boolean
  updating: boolean
  error: string | null
  refetch: () => void
  updateLanguagePreferences: (qids: string[]) => Promise<void>
  updateCountryPreferences: (qids: string[]) => Promise<void>
}

const STORAGE_KEY_INITIALIZED = 'poliloom_preferences_initialized'

function isPreferencesInitialized(): boolean {
  return localStorage.getItem(STORAGE_KEY_INITIALIZED) === 'true'
}

function markPreferencesInitialized(): void {
  localStorage.setItem(STORAGE_KEY_INITIALIZED, 'true')
}

async function getDefaultLanguagesFromBrowser(): Promise<string[]> {
  const response = await fetch('/api/languages')
  if (!response.ok) {
    throw new Error('Failed to fetch languages for default selection')
  }

  const languages: LanguageResponse[] = await response.json()
  const browserLanguages = navigator.languages || [navigator.language]
  const defaultQids: string[] = []

  for (const browserLang of browserLanguages) {
    const baseCode = browserLang.toLowerCase().split('-')[0]
    const matchingLanguage = languages.find(lang =>
      lang.iso1_code === baseCode || lang.iso3_code === baseCode
    )

    if (matchingLanguage && !defaultQids.includes(matchingLanguage.wikidata_id)) {
      defaultQids.push(matchingLanguage.wikidata_id)
    }
  }

  if (defaultQids.length === 0) {
    const english = languages.find(lang =>
      lang.iso1_code === 'en' || lang.iso3_code === 'eng'
    )
    if (english) {
      defaultQids.push(english.wikidata_id)
    }
  }

  return defaultQids
}

export function usePreferences(): UsePreferencesReturn {
  const { status } = useSession()
  const [preferences, setPreferences] = useState<PreferenceResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updatePreferences = useCallback(async (preferenceType: PreferenceType, qids: string[]) => {
    setUpdating(true)
    setError(null)

    try {
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

      await fetchPreferences()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update preferences')
      throw err
    } finally {
      setUpdating(false)
    }
  }, [])

  const fetchPreferences = useCallback(async () => {
    if (status !== 'authenticated') return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/preferences')
      if (!response.ok) {
        throw new Error(`Failed to fetch preferences: ${response.statusText}`)
      }

      const data: PreferenceResponse[] = await response.json()
      setPreferences(data)

      const hasLanguagePrefs = data.some(p => p.preference_type === PreferenceType.LANGUAGE)

      if (!hasLanguagePrefs && !isPreferencesInitialized()) {
        const defaultLanguages = await getDefaultLanguagesFromBrowser()
        if (defaultLanguages.length > 0) {
          await updatePreferences(PreferenceType.LANGUAGE, defaultLanguages)
        }
        markPreferencesInitialized()
      } else if (hasLanguagePrefs) {
        markPreferencesInitialized()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch preferences')
    } finally {
      setLoading(false)
    }
  }, [status, updatePreferences])

  const updateLanguagePreferences = useCallback(async (qids: string[]) => {
    await updatePreferences(PreferenceType.LANGUAGE, qids)
  }, [updatePreferences])

  const updateCountryPreferences = useCallback(async (qids: string[]) => {
    await updatePreferences(PreferenceType.COUNTRY, qids)
  }, [updatePreferences])

  useEffect(() => {
    fetchPreferences()
  }, [fetchPreferences])

  const languagePreferences = preferences
    .filter(p => p.preference_type === PreferenceType.LANGUAGE)
    .map(p => p.qid)

  const countryPreferences = preferences
    .filter(p => p.preference_type === PreferenceType.COUNTRY)
    .map(p => p.qid)

  const languageCount = languagePreferences.length
  const countryCount = countryPreferences.length

  return {
    preferences,
    languagePreferences,
    countryPreferences,
    languageCount,
    countryCount,
    loading,
    updating,
    error,
    refetch: fetchPreferences,
    updateLanguagePreferences,
    updateCountryPreferences
  }
}