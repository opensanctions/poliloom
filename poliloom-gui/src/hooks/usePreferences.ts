"use client"

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { PreferenceResponse, PreferenceType } from '@/types'

interface UsePreferencesReturn {
  preferences: PreferenceResponse[]
  languageCount: number
  countryCount: number
  loading: boolean
  error: string | null
  refetch: () => void
}

export function usePreferences(): UsePreferencesReturn {
  const { status } = useSession()
  const [preferences, setPreferences] = useState<PreferenceResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchPreferences = async () => {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch preferences')
      console.error('Error fetching preferences:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPreferences()
  }, [status])

  const languageCount = preferences.filter(p => p.preference_type === PreferenceType.LANGUAGE).length
  const countryCount = preferences.filter(p => p.preference_type === PreferenceType.COUNTRY).length

  return {
    preferences,
    languageCount,
    countryCount,
    loading,
    error,
    refetch: fetchPreferences
  }
}