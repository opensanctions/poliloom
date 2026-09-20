'use client'

import { useEffect, useState } from 'react'
import { useFilters } from '@/contexts/FilterContext'
import type { LanguageResponse } from '@/types'

/**
 * Wikimedia language codes for the user's selected filter languages, in
 * selection order. Languages without a `wikimedia_code` are skipped.
 */
export function useUserLanguageCodes(): string[] {
  const { languageQids } = useFilters()
  const [codes, setCodes] = useState<string[]>([])

  useEffect(() => {
    const controller = new AbortController()

    async function run() {
      try {
        const response = await fetch('/api/languages', { signal: controller.signal })
        if (!response.ok) return
        const languages: LanguageResponse[] = await response.json()
        const codeByQid = new Map(
          languages.map((language) => [language.wikidata_id, language.wikimedia_code]),
        )
        setCodes(
          languageQids
            .map((qid) => codeByQid.get(qid))
            .filter((code): code is string => typeof code === 'string'),
        )
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
      }
    }

    run()

    return () => controller.abort()
  }, [languageQids])

  return codes
}
