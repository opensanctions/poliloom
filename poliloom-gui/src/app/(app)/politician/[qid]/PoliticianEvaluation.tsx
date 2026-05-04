'use client'

import { useCallback, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Politician,
  PatchPropertiesRequest,
  PatchPropertiesResponse,
  PropertyActionItem,
  SourceResponse,
} from '@/types'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useSettings } from '@/contexts/SettingsContext'
import { useFilters } from '@/contexts/FilterContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
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
  const router = useRouter()
  const { isSessionActive, completedCount, sessionGoal, submitAndAdvance } = useEvaluationSession()
  const { settings, patch } = useSettings()
  const { languageQids } = useFilters()
  const statsUnlocked = settings?.stats_unlocked ?? false
  const isAdvancedMode = settings?.advanced_mode ?? false
  const { nextHref, loading: nextLoading } = useNextPoliticianContext()
  const [politician, setPolitician] = useState<Politician>(initialPolitician)
  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSelection(initialPolitician, languageQids),
  )
  const pendingSourceIdsRef = useRef<Set<string>>(new Set())

  const refetchPolitician = useCallback(async (): Promise<Politician | null> => {
    try {
      const res = await fetch(`/api/politicians/${politician.wikidata_id}`)
      if (!res.ok) return null
      const data: Politician = await res.json()
      setPolitician(data)
      return data
    } catch {
      return null
    }
  }, [politician.wikidata_id])

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

  const handleSubmit = async (actions: PropertyActionItem[]) => {
    const requestData: PatchPropertiesRequest = { items: actions }
    const response = await fetch(`/api/politicians/${politician.wikidata_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestData),
    })

    if (!response.ok) {
      throw new Error(`Failed to submit evaluations: ${response.statusText}`)
    }

    const result: PatchPropertiesResponse = await response.json()
    if (!result.success) {
      console.error('Evaluation errors:', result.errors)
      throw new Error(`Error submitting evaluations: ${result.message}`)
    }

    refetchPolitician()

    if (isSessionActive) {
      const { sessionComplete } = submitAndAdvance()
      if (sessionComplete) {
        router.push(statsUnlocked ? '/session/complete' : '/session/unlocked')
      } else {
        router.push(nextHref)
      }
    }
  }

  const footer = ({ actions, isSubmitting, submit }: FooterContext) => {
    const hasActions = actions.length > 0
    return (
      <div className="flex justify-between items-center">
        {isSessionActive && (
          <div className="text-base text-foreground">
            Progress:{' '}
            <strong>
              {completedCount} / {sessionGoal}
            </strong>{' '}
            politicians evaluated
          </div>
        )}
        <div className="ml-auto">
          {isSessionActive && !hasActions ? (
            <Button
              href={nextLoading ? undefined : nextHref}
              disabled={nextLoading}
              className="px-6 py-3"
            >
              Skip Politician
            </Button>
          ) : (
            <Button
              onClick={submit}
              disabled={isSubmitting || !hasActions || (isSessionActive && nextLoading)}
              className="px-6 py-3"
            >
              {isSubmitting
                ? 'Submitting...'
                : isSessionActive
                  ? 'Submit Evaluations & Next'
                  : 'Submit Evaluations'}
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <EvaluationView
      politician={politician}
      selection={selection}
      onSelectionChange={setSelection}
      onSubmit={handleSubmit}
      footer={footer}
      isAdvancedMode={isAdvancedMode}
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
