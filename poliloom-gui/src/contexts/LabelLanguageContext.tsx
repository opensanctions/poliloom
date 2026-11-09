'use client'

import React, { createContext, useContext } from 'react'

const LabelLanguageContext = createContext<string[] | undefined>(undefined)

/**
 * Carries the browser's preferred language codes for entity labels, resolved
 * on the server so the server and client render the same labels.
 */
export function LabelLanguageProvider({
  languages,
  children,
}: {
  languages: string[]
  children: React.ReactNode
}) {
  return <LabelLanguageContext.Provider value={languages}>{children}</LabelLanguageContext.Provider>
}

export function useLabelLanguages(): string[] {
  const context = useContext(LabelLanguageContext)
  if (context === undefined) {
    throw new Error('useLabelLanguages must be used within a LabelLanguageProvider')
  }
  return context
}
