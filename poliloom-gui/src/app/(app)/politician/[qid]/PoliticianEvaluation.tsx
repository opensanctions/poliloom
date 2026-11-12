'use client'

import { useCallback, useRef, useState } from 'react'
import { PatchActionsResponse, Politician, ReviewSubmitPayload, SourceResponse } from '@/types'
import { useFilters } from '@/contexts/FilterContext'
import { useClaimPolitician } from '@/hooks/useClaimPolitician'
import { useEventStream } from '@/contexts/EventStreamContext'
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
  const { languageQids } = useFilters()
  const { claimAndNavigate, isClaiming } = useClaimPolitician()
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
      const next = findSelectionForSource(updated, event.source_id)
      if (!next) return
      // A source the user just added takes over the view; otherwise only fill
      // an empty view so an ingestion result never replaces what is being read.
      if (pendingSourceIdsRef.current.delete(event.source_id)) {
        setSelection(next)
      } else {
        setSelection((current) => current ?? next)
      }
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

      await claimAndNavigate()
    },
    [politician.wikidata_id, claimAndNavigate],
  )

  const footer = ({ decidedCount, isSubmitting, submit: submitDecisions }: FooterContext) => {
    const hasDecisions = decidedCount > 0
    const disabled = isSubmitting || isClaiming
    return (
      <div className="flex justify-end">
        {!hasDecisions ? (
          <Button onClick={submitDecisions} disabled={disabled} className="px-6 py-3">
            {isSubmitting ? 'Skipping...' : 'Skip Politician'}
          </Button>
        ) : (
          <Button onClick={submitDecisions} disabled={disabled} className="px-6 py-3">
            {isSubmitting ? 'Submitting...' : 'Submit Decisions & Next'}
          </Button>
        )}
      </div>
    )
  }

  return (
    <EvaluationView
      politician={politician}
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
