'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { NextPoliticianResponse, PreferenceType, EnrichmentMetadata } from '@/types'

export function useNextPolitician(excludeId?: string) {
  const { filters } = useUserPreferences()

  const [nextQid, setNextQid] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [enrichmentMeta, setEnrichmentMeta] = useState<EnrichmentMetadata | null>(null)

  const languageFilters = useMemo(
    () =>
      filters
        .filter((p) => p.preference_type === PreferenceType.LANGUAGE)
        .map((p) => p.wikidata_id),
    [filters],
  )

  const countryFilters = useMemo(
    () =>
      filters.filter((p) => p.preference_type === PreferenceType.COUNTRY).map((p) => p.wikidata_id),
    [filters],
  )

  const fetchNext = useCallback(async () => {
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
  }, [languageFilters, countryFilters, excludeId])

  // Fetch on mount and when filters change
  useEffect(() => {
    fetchNext()
  }, [fetchNext])

  // Auto-poll when waiting for enrichment
  useEffect(() => {
    if (nextQid !== null) return
    if (!enrichmentMeta?.has_enrichable_politicians) return

    const pollInterval = setInterval(fetchNext, 5000)
    return () => clearInterval(pollInterval)
  }, [nextQid, enrichmentMeta?.has_enrichable_politicians, fetchNext])

  const nextHref = nextQid ? `/politician/${nextQid}` : null

  return { nextQid, nextHref, loading, enrichmentMeta }
}
