'use client'

import React, { createContext, useCallback, useContext, useState } from 'react'
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
  const [languageQids, setLanguageQids] = useState<string[]>(initialLanguageQids)
  const [countryQids, setCountryQids] = useState<string[]>(initialCountryQids)

  const setLanguages = useCallback((qids: string[]) => {
    if (qids.length === 0) return
    writeFilterCookie(FILTER_LANGUAGES_COOKIE, qids)
    setLanguageQids(qids)
  }, [])

  const setCountries = useCallback((qids: string[]) => {
    writeFilterCookie(FILTER_COUNTRIES_COOKIE, qids)
    setCountryQids(qids)
  }, [])

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
