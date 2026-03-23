'use client'

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useEventStream } from '@/contexts/EventStreamContext'
import { NextPoliticianResponse, PreferenceType, EnrichmentMetadata } from '@/types'

interface NextPoliticianContextType {
  nextQid: string | null
  nextHref: string | null
  loading: boolean
  enrichmentMeta: EnrichmentMetadata | null
  languageFilters: string[]
  countryFilters: string[]
  advanceNext: () => void
}

const NextPoliticianContext = createContext<NextPoliticianContextType | undefined>(undefined)

export function NextPoliticianProvider({ children }: { children: React.ReactNode }) {
  const { filters } = useUserPreferences()

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

  const fetchNext = useCallback(
    async (excludeId?: string) => {
      setLoading(true)
      try {
        const params = new URLSearchParams()
        languageFilters.forEach((qid) => params.append('languages', qid))
        countryFilters.forEach((qid) => params.append('countries', qid))
        if (excludeId) params.append('exclude_ids', excludeId)

        const response = await fetch(`/api/politicians/next?${params.toString()}`)
        if (!response.ok) return

        const data: NextPoliticianResponse = await response.json()
        setNextQid(data.wikidata_id)
        setEnrichmentMeta(data.meta)
      } catch {
        // Ignore errors
      } finally {
        setLoading(false)
      }
    },
    [languageFilters, countryFilters],
  )

  // Fetch on mount and when filters change, excluding the currently held id
  // Wait for filters to load from localStorage before fetching,
  // otherwise the first call fires with empty filters.
  useEffect(() => {
    if (filters === undefined) return
    fetchNext(nextQid ?? undefined)
    // nextQid intentionally excluded — we only want to re-fetch when filters change, not when nextQid changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const advanceNext = useCallback(() => {
    fetchNext(nextQid ?? undefined)
  }, [fetchNext, nextQid])

  const nextHref = nextQid ? `/politician/${nextQid}` : null

  const value: NextPoliticianContextType = {
    nextQid,
    nextHref,
    loading,
    enrichmentMeta,
    languageFilters,
    countryFilters,
    advanceNext,
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
