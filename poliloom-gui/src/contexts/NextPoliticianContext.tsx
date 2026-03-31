'use client'

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'next/navigation'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useEventStream } from '@/contexts/EventStreamContext'
import { NextPoliticianResponse, PreferenceType, EnrichmentMetadata } from '@/types'

interface NextPoliticianContextType {
  nextHref: string
  politicianReady: boolean
  allCaughtUp: boolean
  loading: boolean
  languageFilters: string[]
  countryFilters: string[]
}

const NextPoliticianContext = createContext<NextPoliticianContextType | undefined>(undefined)

export function NextPoliticianProvider({ children }: { children: React.ReactNode }) {
  const { filters } = useUserPreferences()
  const params = useParams()
  const currentQid = (params?.qid as string) ?? null

  const [nextQid, setNextQid] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [enrichmentMeta, setEnrichmentMeta] = useState<EnrichmentMetadata | null>(null)

  const languageFilters = useMemo(
    () =>
      filters
        ?.filter((p) => p.preference_type === PreferenceType.LANGUAGE)
        .map((p) => p.wikidata_id) ?? [],
    [filters],
  )

  const countryFilters = useMemo(
    () =>
      filters
        ?.filter((p) => p.preference_type === PreferenceType.COUNTRY)
        .map((p) => p.wikidata_id) ?? [],
    [filters],
  )

  const fetchNext = useCallback(async () => {
    setLoading(true)
    try {
      const searchParams = new URLSearchParams()
      languageFilters.forEach((qid) => searchParams.append('languages', qid))
      countryFilters.forEach((qid) => searchParams.append('countries', qid))
      if (currentQid) searchParams.append('exclude_ids', currentQid)

      const response = await fetch(`/api/politicians/next?${searchParams.toString()}`)
      if (!response.ok) return

      const data: NextPoliticianResponse = await response.json()
      setNextQid(data.wikidata_id)
      setEnrichmentMeta(data.meta)
    } catch {
      // Ignore errors
    } finally {
      setLoading(false)
    }
  }, [languageFilters, countryFilters, currentQid])

  // Fetch when filters or current route change.
  // Wait for filters to load from localStorage before fetching,
  // otherwise the first call fires with empty filters.
  useEffect(() => {
    if (filters === undefined) return
    fetchNext()
  }, [fetchNext, filters !== undefined])

  // Listen for enrichment_complete events instead of polling
  useEventStream(
    'enrichment_complete',
    (event) => {
      if (nextQid !== null) return
      const languageMatch =
        languageFilters.length === 0 || event.languages.some((l) => languageFilters.includes(l))
      const countryMatch =
        countryFilters.length === 0 || event.countries.some((c) => countryFilters.includes(c))
      if (languageMatch && countryMatch) {
        fetchNext()
      }
    },
    [nextQid, languageFilters, countryFilters, fetchNext],
  )

  const politicianReady = nextQid !== null
  const hasEnrichablePoliticians = enrichmentMeta?.has_enrichable_politicians ?? false
  const politicianHref = nextQid ? `/politician/${nextQid}` : null
  const nextHref = politicianHref ?? (hasEnrichablePoliticians ? '/session/enriching' : '/')

  const allCaughtUp = !loading && !politicianReady && !hasEnrichablePoliticians

  const value: NextPoliticianContextType = {
    nextHref,
    politicianReady,
    allCaughtUp,
    loading,
    languageFilters,
    countryFilters,
  }

  return <NextPoliticianContext.Provider value={value}>{children}</NextPoliticianContext.Provider>
}

export function useNextPoliticianContext() {
  const context = useContext(NextPoliticianContext)
  if (context === undefined) {
    throw new Error('useNextPoliticianContext must be used within a NextPoliticianProvider')
  }
  return context
}
