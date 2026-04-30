'use client'

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
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
  const { user, pending } = useUser()
  const params = useParams()
  const currentQid = (params?.qid as string) ?? null

  const [nextQid, setNextQid] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [enrichmentMeta, setEnrichmentMeta] = useState<EnrichmentMetadata | null>(null)

  const fetchNext = useCallback(async () => {
    setLoading(true)
    try {
      const url = currentQid
        ? `/api/politicians/next?exclude_ids=${encodeURIComponent(currentQid)}`
        : '/api/politicians/next'
      const response = await fetch(url)
      if (!response.ok) return

      const data: NextPoliticianResponse = await response.json()
      setNextQid(data.wikidata_id)
      setEnrichmentMeta(data.meta)
    } catch {
      // Ignore errors
    } finally {
      setLoading(false)
    }
  }, [currentQid])

  const userLoaded = user !== undefined
  useEffect(() => {
    if (!userLoaded || pending) return
    fetchNext()
  }, [fetchNext, user?.filters, userLoaded, pending])

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
