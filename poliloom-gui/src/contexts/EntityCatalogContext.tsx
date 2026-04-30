'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { CountryResponse, LanguageResponse } from '@/types'

interface EntityCatalogContextType {
  languages: LanguageResponse[]
  countries: CountryResponse[]
  loadingLanguages: boolean
  loadingCountries: boolean
}

const EntityCatalogContext = createContext<EntityCatalogContextType | undefined>(undefined)

function useFetchOnAuth<T>(url: string): { data: T[]; loading: boolean } {
  const { status } = useSession()
  const [data, setData] = useState<T[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (status !== 'authenticated') return
    let cancelled = false
    ;(async () => {
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error(`GET ${url}: ${response.status}`)
        const json = (await response.json()) as T[]
        if (!cancelled) setData(json)
      } catch (error) {
        console.warn(`Failed to fetch ${url}:`, error)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [status, url])

  return { data, loading }
}

export function EntityCatalogProvider({ children }: { children: React.ReactNode }) {
  const { data: languages, loading: loadingLanguages } =
    useFetchOnAuth<LanguageResponse>('/api/languages')
  const { data: countries, loading: loadingCountries } =
    useFetchOnAuth<CountryResponse>('/api/countries')

  return (
    <EntityCatalogContext.Provider
      value={{ languages, countries, loadingLanguages, loadingCountries }}
    >
      {children}
    </EntityCatalogContext.Provider>
  )
}

export function useEntityCatalog() {
  const context = useContext(EntityCatalogContext)
  if (context === undefined) {
    throw new Error('useEntityCatalog must be used within an EntityCatalogProvider')
  }
  return context
}
