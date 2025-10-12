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

  const buildQueryParams = useCallback(
    (limit: number = 1, offset: number = 0) => {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        has_unevaluated: 'true',
      })
      languagePreferences.forEach((qid) => params.append('languages', qid))
      countryPreferences.forEach((qid) => params.append('countries', qid))
      return params
    },
    [languagePreferences, countryPreferences],
  )

  const fetchPoliticians = useCallback(
    async (limit: number = 1, offset: number = 0): Promise<Politician[]> => {
      if (!session?.accessToken) return []

      const params = buildQueryParams(limit, offset)
      const response = await fetch(`/api/politicians?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch politicians: ${response.statusText}`)
      }

      return response.json()
    },
    [session?.accessToken, buildQueryParams],
  )

  // Clear politicians when preferences change
  useEffect(() => {
    setCurrentPolitician(null)
    setNextPolitician(null)
  }, [languagePreferences, countryPreferences])

  // Fetch politicians when current is null
  useEffect(() => {
    if (!isAuthenticated || !initialized || loading) return
    if (currentPolitician !== null) return

    // Set loading immediately to prevent re-entry
    setLoading(true)

    const fetch = async () => {
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
    }

    fetch()
  }, [isAuthenticated, initialized, fetchPoliticians, currentPolitician])

  const refetch = useCallback(() => {
    // Immediately move next to current for instant UI update
    setCurrentPolitician(nextPolitician)
    setNextPolitician(null)

    // Fetch new next politician in the background with offset=1 to skip the current one
    if (nextPolitician) {
      fetchPoliticians(1, 1)
        .then((politicians) => {
          if (politicians.length > 0) {
            setNextPolitician(politicians[0])
          }
        })
        .catch((err) => {
          console.error('Error fetching next politician:', err)
        })
    }
  }, [nextPolitician, fetchPoliticians])

  const value: PoliticiansContextType = {
    currentPolitician,
    nextPolitician,
    loading,
    refetch,
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
