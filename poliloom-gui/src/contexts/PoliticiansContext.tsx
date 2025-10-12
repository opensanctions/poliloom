'use client'

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { Politician, PreferenceType } from '@/types'
import { useAuthSession } from '@/hooks/useAuthSession'
import { usePreferencesContext } from './PreferencesContext'

interface PoliticiansContextType {
  currentPolitician: Politician | null
  nextPolitician: Politician | null
  loading: boolean
  refetch: () => void
  loadPoliticians: () => Promise<void>
}

const PoliticiansContext = createContext<PoliticiansContextType | undefined>(undefined)

export function PoliticiansProvider({ children }: { children: React.ReactNode }) {
  const { session, isAuthenticated } = useAuthSession()
  const { preferences, initialized } = usePreferencesContext()
  const [currentPolitician, setCurrentPolitician] = useState<Politician | null>(null)
  const [nextPolitician, setNextPolitician] = useState<Politician | null>(null)
  const [loading, setLoading] = useState(false)

  // Memoize preference arrays to prevent unnecessary recreations
  const languagePreferences = useMemo(
    () =>
      preferences
        .filter((p) => p.preference_type === PreferenceType.LANGUAGE)
        .map((p) => p.wikidata_id),
    [preferences],
  )

  const countryPreferences = useMemo(
    () =>
      preferences
        .filter((p) => p.preference_type === PreferenceType.COUNTRY)
        .map((p) => p.wikidata_id),
    [preferences],
  )

  const fetchPoliticians = useCallback(
    async (limit: number = 1): Promise<Politician[]> => {
      if (!session?.accessToken) return []

      const params = new URLSearchParams({
        limit: limit.toString(),
        has_unevaluated: 'true',
      })
      languagePreferences.forEach((qid) => params.append('languages', qid))
      countryPreferences.forEach((qid) => params.append('countries', qid))

      const response = await fetch(`/api/politicians?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch politicians: ${response.statusText}`)
      }

      return response.json()
    },
    [session?.accessToken, languagePreferences, countryPreferences],
  )

  // Clear politicians when preferences change
  useEffect(() => {
    setCurrentPolitician(null)
    setNextPolitician(null)
  }, [languagePreferences, countryPreferences])

  const loadPoliticians = useCallback(async () => {
    if (!isAuthenticated || !initialized) return

    setLoading(true)
    try {
      const politicians = await fetchPoliticians(2)

      if (politicians.length > 0) {
        setCurrentPolitician(politicians[0])
        setNextPolitician(politicians[1] || null)
      }
    } catch (err) {
      console.error('Error fetching politicians:', err)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, initialized, fetchPoliticians])

  // Fetch politicians when current is null
  // Note: loading is intentionally excluded from dependencies as it's a guard condition
  // to prevent fetching while already loading. Including it would cause unnecessary re-runs.
  useEffect(() => {
    if (!isAuthenticated || !initialized || loading) return
    if (currentPolitician !== null) return

    loadPoliticians()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, initialized, currentPolitician, loadPoliticians])

  const refetch = useCallback(async () => {
    // Immediately move next to current for instant UI update
    setCurrentPolitician(nextPolitician)
    setNextPolitician(null)

    // Fetch new next politician in the background
    if (nextPolitician) {
      try {
        const politicians = await fetchPoliticians(1)
        if (politicians.length > 0) {
          setNextPolitician(politicians[0])
        }
      } catch (err) {
        console.error('Error fetching next politician:', err)
      }
    }
  }, [nextPolitician, fetchPoliticians])

  const value: PoliticiansContextType = {
    currentPolitician,
    nextPolitician,
    loading,
    refetch,
    loadPoliticians,
  }

  return <PoliticiansContext.Provider value={value}>{children}</PoliticiansContext.Provider>
}

export function usePoliticians() {
  const context = useContext(PoliticiansContext)
  if (context === undefined) {
    throw new Error('usePoliticians must be used within a PoliticiansProvider')
  }
  return context
}
