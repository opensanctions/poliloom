'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Politician,
  PropertyWithEvaluation,
  EvaluationRequest,
  EvaluationResponse,
  SubmissionItem,
} from '@/types'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { Button } from '@/components/ui/Button'
import { PoliticianEvaluationView } from '@/components/evaluation/PoliticianEvaluationView'

interface PoliticianEvaluationProps {
  politician: Politician
}

export function PoliticianEvaluation({ politician }: PoliticianEvaluationProps) {
  const router = useRouter()
  const { isSessionActive, completedCount, sessionGoal, submitAndAdvance } = useEvaluationSession()
  const { statsUnlocked, completeBasicTutorial, completeAdvancedTutorial } = useUserProgress()
  const { isAdvancedMode } = useUserPreferences()
  const {
    nextHref: nextPoliticianHref,
    advanceNext,
    loading: nextLoading,
  } = useNextPoliticianContext()
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Mark tutorials complete and prefetch next politician on mount
  useEffect(() => {
    completeBasicTutorial()
    if (isAdvancedMode) {
      completeAdvancedTutorial()
    }
    advanceNext()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = async (properties: PropertyWithEvaluation[]) => {
    setIsSubmitting(true)

    const items: SubmissionItem[] = properties
      .filter((p) => p.evaluation !== undefined || !p.id)
      .map((p) => {
        if (p.id) {
          // Existing property → evaluation
          return { id: p.id, is_accepted: p.evaluation }
        }
        // User-created property → creation
        return {
          type: p.type,
          value: p.value,
          value_precision: p.value_precision,
          entity_id: p.entity_id,
          qualifiers_json: p.qualifiers as Record<string, unknown> | undefined,
        }
      })

    try {
      const evaluationData: EvaluationRequest = {
        politician_id: politician.id,
        items,
      }
      const response = await fetch('/api/evaluations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(evaluationData),
      })

      if (!response.ok) {
        throw new Error(`Failed to submit evaluations: ${response.statusText}`)
      }

      const result: EvaluationResponse = await response.json()
      if (!result.success) {
        console.error('Evaluation errors:', result.errors)
        alert(`Error submitting evaluations: ${result.message}`)
        return
      }

      if (isSessionActive) {
        const { sessionComplete } = submitAndAdvance()
        if (sessionComplete) {
          router.push(statsUnlocked ? '/session/complete' : '/session/unlocked')
        } else {
          router.push(nextPoliticianHref ?? '/session/enriching')
        }
      }
    } catch (error) {
      console.error('Submission failed:', error)
      alert('Error submitting evaluations. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const hasChanges = (properties: PropertyWithEvaluation[]) =>
    properties.some((p) => p.evaluation !== undefined || !p.id)

  // Session mode footer
  const sessionFooter = (properties: PropertyWithEvaluation[]) => (
    <div className="flex justify-between items-center">
      <div className="text-base text-foreground">
        Progress:{' '}
        <strong>
          {completedCount} / {sessionGoal}
        </strong>{' '}
        politicians evaluated
      </div>
      {!hasChanges(properties) ? (
        <Button
          href={nextPoliticianHref ?? (nextLoading ? undefined : '/session/enriching')}
          disabled={nextLoading}
          className="px-6 py-3"
        >
          Skip Politician
        </Button>
      ) : (
        <Button
          onClick={() => handleSubmit(properties)}
          disabled={isSubmitting || nextLoading}
          className="px-6 py-3"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Evaluations & Next'}
        </Button>
      )}
    </div>
  )

  // Standalone mode footer
  const standaloneFooter = (properties: PropertyWithEvaluation[]) => (
    <div className="flex justify-end items-center">
      <Button
        onClick={() => handleSubmit(properties)}
        disabled={isSubmitting || !hasChanges(properties)}
        className="px-6 py-3"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Evaluations'}
      </Button>
    </div>
  )

  return (
    <PoliticianEvaluationView
      politician={politician}
      footer={isSessionActive ? sessionFooter : standaloneFooter}
    />
  )
}
