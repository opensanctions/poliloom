'use client'

import React, { createContext, useCallback, useContext, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { FILTER_COUNTRIES_COOKIE, FILTER_LANGUAGES_COOKIE, writeFilterCookie } from '@/lib/cookies'

interface FilterContextType {
  languageQids: string[]
  countryQids: string[]
  setLanguages: (qids: string[]) => void
  setCountries: (qids: string[]) => void
}

const FilterContext = createContext<FilterContextType | undefined>(undefined)

export function FilterProvider({
  initialLanguageQids,
  initialCountryQids,
  children,
}: {
  initialLanguageQids: string[]
  initialCountryQids: string[]
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [languageQids, setLanguageQids] = useState<string[]>(initialLanguageQids)
  const [countryQids, setCountryQids] = useState<string[]>(initialCountryQids)

  const syncUrl = useCallback(
    (langs: string[], countries: string[]) => {
      const params = new URLSearchParams(searchParams.toString())
      params.delete('languages')
      params.delete('countries')
      for (const qid of langs) params.append('languages', qid)
      for (const qid of countries) params.append('countries', qid)
      const qs = params.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [pathname, router, searchParams],
  )

  const setLanguages = useCallback(
    (qids: string[]) => {
      writeFilterCookie(FILTER_LANGUAGES_COOKIE, qids)
      setLanguageQids(qids)
      syncUrl(qids, countryQids)
    },
    [countryQids, syncUrl],
  )

  const setCountries = useCallback(
    (qids: string[]) => {
      writeFilterCookie(FILTER_COUNTRIES_COOKIE, qids)
      setCountryQids(qids)
      syncUrl(languageQids, qids)
    },
    [languageQids, syncUrl],
  )

  return (
    <FilterContext.Provider value={{ languageQids, countryQids, setLanguages, setCountries }}>
      {children}
    </FilterContext.Provider>
  )
}

export function useFilters() {
  const context = useContext(FilterContext)
  if (context === undefined) {
    throw new Error('useFilters must be used within a FilterProvider')
  }
  return context
}
