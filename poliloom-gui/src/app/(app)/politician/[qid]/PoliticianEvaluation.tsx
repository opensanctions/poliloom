'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
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

export function PoliticianEvaluation({ politician }: PoliticianEvaluationProps) {
  const router = useRouter()
  const { languageQids } = useFilters()
  const { claimAndNavigate, isClaiming } = useClaimPolitician()
  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSelection(politician, languageQids),
  )
  const pendingSourceIdsRef = useRef<Set<string>>(new Set())
  const completedSourceIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    for (const sourceId of completedSourceIdsRef.current) {
      const next = findSelectionForSource(politician, sourceId)
      completedSourceIdsRef.current.delete(sourceId)
      if (!next) continue
      // A source the user just added takes over the view; otherwise only fill
      // an empty view so an ingestion result never replaces what is being read.
      if (pendingSourceIdsRef.current.delete(sourceId)) {
        setSelection(next)
      } else {
        setSelection((current) => current ?? next)
      }
    }
  }, [politician])

  useEventStream(
    'source_status',
    (event) => {
      if (!event.politician_ids.includes(politician.id)) return
      if (event.status === 'done') completedSourceIdsRef.current.add(event.source_id)
      router.refresh()
    },
    [politician.id, router],
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
      if (!result.success || result.errors.length > 0) {
        router.refresh()
        return result
      }

      try {
        await claimAndNavigate()
      } catch (error) {
        router.refresh()
        throw error
      }
      return result
    },
    [politician.wikidata_id, claimAndNavigate, router],
  )

  const footer = ({
    decidedCount,
    isSubmitting,
    submit: submitDecisions,
    applicationErrors,
  }: FooterContext) => {
    const hasDecisions = decidedCount > 0
    const disabled = isSubmitting || isClaiming
    if (applicationErrors.length > 0) {
      return (
        <div className="flex justify-end">
          <Button onClick={claimAndNavigate} disabled={disabled} className="px-6 py-3">
            {isClaiming ? 'Loading...' : 'Next Politician'}
          </Button>
        </div>
      )
    }
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
        router.refresh()
      }}
    />
  )
}
