'use client'

import React, { createContext, useContext } from 'react'
import { useNextPolitician } from '@/hooks/useNextPolitician'
import { EnrichmentMetadata } from '@/types'

interface NextPoliticianContextType {
  nextQid: string | null
  nextHref: string | null
  loading: boolean
  enrichmentMeta: EnrichmentMetadata | null
  languageFilters: string[]
  countryFilters: string[]
}

const NextPoliticianContext = createContext<NextPoliticianContextType | undefined>(undefined)

export function NextPoliticianProvider({ children }: { children: React.ReactNode }) {
  const value = useNextPolitician()
  return <NextPoliticianContext.Provider value={value}>{children}</NextPoliticianContext.Provider>
}

export function useNextPoliticianContext() {
  const context = useContext(NextPoliticianContext)
  if (context === undefined) {
    throw new Error('useNextPoliticianContext must be used within a NextPoliticianProvider')
  }
  return context
}
