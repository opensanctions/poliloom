'use client'

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useFilters } from '@/contexts/FilterContext'
import { useEventStream } from '@/contexts/EventStreamContext'
import { NextPoliticianResponse, EnrichmentMetadata } from '@/types'

interface NextPoliticianContextType {
  nextHref: string
  politicianReady: boolean
  allCaughtUp: boolean
  loading: boolean
}

const NextPoliticianContext = createContext<NextPoliticianContextType | undefined>(undefined)

export function NextPoliticianProvider({ children }: { children: React.ReactNode }) {
  const { languageQids, countryQids } = useFilters()
  const params = useParams()
  const currentQid = (params?.qid as string) ?? null

  const [nextQid, setNextQid] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [enrichmentMeta, setEnrichmentMeta] = useState<EnrichmentMetadata | null>(null)

  const inFlightRef = useRef<AbortController | null>(null)

  const fetchNext = useCallback(async () => {
    inFlightRef.current?.abort()
    const controller = new AbortController()
    inFlightRef.current = controller
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (currentQid) params.set('exclude_ids', currentQid)
      for (const qid of languageQids) params.append('languages', qid)
      for (const qid of countryQids) params.append('countries', qid)
      const qs = params.toString()
      const url = `/api/politicians/next${qs ? `?${qs}` : ''}`
      const response = await fetch(url, { signal: controller.signal })
      if (!response.ok) return

      const data: NextPoliticianResponse = await response.json()
      setNextQid(data.wikidata_id)
      setEnrichmentMeta(data.meta)
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
    } finally {
      if (!controller.signal.aborted) {
        inFlightRef.current = null
        setLoading(false)
      }
    }
  }, [currentQid, languageQids, countryQids])

  useEffect(() => {
    fetchNext()
    return () => inFlightRef.current?.abort()
  }, [fetchNext])

  useEventStream(
    'enrichment_complete',
    () => {
      if (nextQid === null) fetchNext()
    },
    [nextQid, fetchNext],
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
