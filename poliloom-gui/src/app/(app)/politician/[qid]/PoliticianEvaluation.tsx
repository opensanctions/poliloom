'use client'

import { useCallback, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { PatchActionsResponse, Politician, ReviewSubmitPayload, SourceResponse } from '@/types'
import { useFilters } from '@/contexts/FilterContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { useEventStream } from '@/contexts/EventStreamContext'
import { useUserLanguageCodes } from '@/hooks/useUserLanguageCodes'
import { Button } from '@/components/ui/Button'
import {
  EvaluationView,
  FooterContext,
  SourceSelection,
  findInitialSelection,
  findSelectionForSource,
} from '@/components/evaluation/EvaluationView'

interface PoliticianEvaluationProps {
  politician: Politician
}

export function PoliticianEvaluation({ politician: initialPolitician }: PoliticianEvaluationProps) {
  const router = useRouter()
  const { languageQids } = useFilters()
  const userLanguageCodes = useUserLanguageCodes()
  const { nextHref, loading: nextLoading } = useNextPoliticianContext()
  const [politician, setPolitician] = useState<Politician>(initialPolitician)
  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSelection(initialPolitician, languageQids),
  )
  const pendingSourceIdsRef = useRef<Set<string>>(new Set())

  const refetchPolitician = useCallback(async (): Promise<Politician | null> => {
    try {
      const searchParams = new URLSearchParams()
      for (const languageQid of languageQids) {
        searchParams.append('languages', languageQid)
      }
      const qs = searchParams.toString()
      const res = await fetch(`/api/politicians/${politician.wikidata_id}${qs ? `?${qs}` : ''}`)
      if (!res.ok) return null
      const data: Politician = await res.json()
      setPolitician(data)
      return data
    } catch {
      return null
    }
  }, [politician.wikidata_id, languageQids])

  useEventStream(
    'source_status',
    async (event) => {
      if (!event.politician_ids.includes(politician.id)) return
      if (event.status !== 'done') {
        refetchPolitician()
        return
      }
      const updated = await refetchPolitician()
      if (!updated) return
      if (!pendingSourceIdsRef.current.has(event.source_id)) return
      pendingSourceIdsRef.current.delete(event.source_id)
      const next = findSelectionForSource(updated, event.source_id)
      if (next) setSelection(next)
    },
    [politician.id, refetchPolitician],
  )

  const submit = useCallback(
    async (payload: ReviewSubmitPayload) => {
      const response = await fetch(`/api/politicians/${politician.wikidata_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(`Failed to submit decisions: ${response.statusText}`)
      }

      const result: PatchActionsResponse = await response.json()
      if (!result.success) {
        console.error('Decision errors:', result.errors)
        throw new Error(`Error submitting decisions: ${result.message}`)
      }

      refetchPolitician()
      router.push(nextHref)
    },
    [politician.wikidata_id, refetchPolitician, router, nextHref],
  )

  const footer = ({ decidedCount, isSubmitting, submit: submitDecisions }: FooterContext) => {
    const hasDecisions = decidedCount > 0
    return (
      <div className="flex justify-between items-center">
        <div className="ml-auto">
          {!hasDecisions ? (
            <Button
              onClick={submitDecisions}
              disabled={nextLoading || isSubmitting}
              className="px-6 py-3"
            >
              {isSubmitting ? 'Skipping...' : 'Skip Politician'}
            </Button>
          ) : (
            <Button
              onClick={submitDecisions}
              disabled={isSubmitting || nextLoading}
              className="px-6 py-3"
            >
              {isSubmitting ? 'Submitting...' : 'Submit Decisions & Next'}
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <EvaluationView
      politician={politician}
      userLanguageCodes={userLanguageCodes}
      selection={selection}
      onSelectionChange={setSelection}
      onSubmit={submit}
      footer={footer}
      onAddSource={async (url) => {
        const response = await fetch(`/api/politicians/${politician.wikidata_id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        })
        if (!response.ok) {
          const data = await response.json().catch(() => null)
          throw new Error(data?.detail || `Failed to add source: ${response.statusText}`)
        }
        const created: SourceResponse = await response.json()
        pendingSourceIdsRef.current.add(created.id)
        refetchPolitician()
      }}
    />
  )
}
