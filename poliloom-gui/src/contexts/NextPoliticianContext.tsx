'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
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

  const searchParams = new URLSearchParams()
  if (currentQid) searchParams.set('exclude_ids', currentQid)
  for (const qid of languageQids) searchParams.append('languages', qid)
  for (const qid of countryQids) searchParams.append('countries', qid)
  const query = searchParams.toString()
  const requestUrl = `/api/politicians/next${query ? `?${query}` : ''}`

  const [nextQid, setNextQid] = useState<string | null>(null)
  const [enrichmentMeta, setEnrichmentMeta] = useState<EnrichmentMetadata | null>(null)
  const [refreshNonce, setRefreshNonce] = useState(0)
  const requestKey = `${requestUrl}#${refreshNonce}`
  const [completedRequestKey, setCompletedRequestKey] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    async function run() {
      try {
        const response = await fetch(requestUrl, { signal: controller.signal })
        if (!response.ok) return

        const data: NextPoliticianResponse = await response.json()
        if (cancelled) return
        setNextQid(data.wikidata_id)
        setEnrichmentMeta(data.meta)
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
      } finally {
        if (!cancelled) setCompletedRequestKey(requestKey)
      }
    }

    run()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [requestKey, requestUrl])

  useEventStream(
    'enrichment_complete',
    () => {
      if (nextQid === null) setRefreshNonce((nonce) => nonce + 1)
    },
    [nextQid],
  )

  const loading = completedRequestKey !== requestKey

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
