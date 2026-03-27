'use client'

import { useEffect, useCallback, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Politician,
  PatchPropertiesRequest,
  PatchPropertiesResponse,
  PropertyActionItem,
} from '@/types'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { useEventStream } from '@/contexts/EventStreamContext'
import { Button } from '@/components/ui/Button'
import { EvaluationView, FooterContext } from '@/components/evaluation/EvaluationView'

interface PoliticianEvaluationProps {
  politician: Politician
}

export function PoliticianEvaluation({ politician: initialPolitician }: PoliticianEvaluationProps) {
  const router = useRouter()
  const { isSessionActive, completedCount, sessionGoal, submitAndAdvance } = useEvaluationSession()
  const { statsUnlocked, completeBasicTutorial, completeAdvancedTutorial } = useUserProgress()
  const { isAdvancedMode } = useUserPreferences()
  const { nextHref, advanceNext, loading: nextLoading } = useNextPoliticianContext()
  const [politician, setPolitician] = useState<Politician>(initialPolitician)

  // Mark tutorials complete and prefetch next politician on mount
  useEffect(() => {
    completeBasicTutorial()
    if (isAdvancedMode) {
      completeAdvancedTutorial()
    }
    advanceNext()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const refetchPolitician = useCallback(() => {
    fetch(`/api/politicians/${politician.wikidata_id}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: Politician | null) => {
        if (data) setPolitician(data)
      })
      .catch(() => {})
  }, [politician.wikidata_id])

  // Refetch politician data on source status changes
  useEventStream(
    'source_status',
    (event) => {
      if (!event.politician_ids.includes(politician.id)) return
      refetchPolitician()
    },
    [politician.id, refetchPolitician],
  )

  const handleSubmit = async (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    const actions = actionsByPolitician.get(politician.id) || []
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

  const footer = ({ actionsByPolitician, isSubmitting, submit }: FooterContext) => {
    const actions = actionsByPolitician.get(politician.id) || []
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
      politicians={[politician]}
      onSubmit={handleSubmit}
      footer={footer}
      isAdvancedMode={isAdvancedMode}
      onAddSource={async (qid, url) => {
        const response = await fetch(`/api/politicians/${qid}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        })
        if (!response.ok) {
          const data = await response.json().catch(() => null)
          throw new Error(data?.detail || `Failed to add source: ${response.statusText}`)
        }
        await response.json()
        refetchPolitician()
      }}
    />
  )
}
