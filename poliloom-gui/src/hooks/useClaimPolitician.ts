'use client'

import { useCallback, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useFilters } from '@/contexts/FilterContext'
import type { ClaimPoliticianResponse } from '@/types'

export function useClaimPolitician() {
  const router = useRouter()
  const { languageQids, countryQids } = useFilters()
  const [isClaiming, setIsClaiming] = useState(false)

  const claimAndNavigate = useCallback(async (): Promise<string | null> => {
    setIsClaiming(true)
    try {
      const searchParams = new URLSearchParams()
      for (const qid of languageQids) searchParams.append('languages', qid)
      for (const qid of countryQids) searchParams.append('countries', qid)
      const query = searchParams.toString()

      const response = await fetch(`/api/politicians/claim${query ? `?${query}` : ''}`, {
        method: 'POST',
      })
      if (!response.ok) {
        throw new Error(`Failed to claim politician: ${response.statusText}`)
      }

      const data: ClaimPoliticianResponse = await response.json()
      router.push(data.wikidata_id ? `/politician/${data.wikidata_id}` : '/?empty=1')
      return data.wikidata_id
    } finally {
      setIsClaiming(false)
    }
  }, [router, languageQids, countryQids])

  return { claimAndNavigate, isClaiming }
}
