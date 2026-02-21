'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Politician, EvaluationItem, EvaluationRequest, EvaluationResponse } from '@/types'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useNextPolitician } from '@/hooks/useNextPolitician'
import { Button } from '@/components/ui/Button'
import { PoliticianEvaluationView } from './PoliticianEvaluationView'

interface PoliticianClientProps {
  politician: Politician
}

export function PoliticianClient({ politician }: PoliticianClientProps) {
  const router = useRouter()
  const { isSessionActive, completedCount, sessionGoal, submitAndAdvance } = useEvaluationSession()
  const { statsUnlocked, completeBasicTutorial, completeAdvancedTutorial } = useUserProgress()
  const { isAdvancedMode } = useUserPreferences()
  const { nextHref: nextPoliticianHref } = useNextPolitician(politician.wikidata_id ?? undefined)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Mark tutorials complete on mount
  useEffect(() => {
    completeBasicTutorial()
    if (isAdvancedMode) {
      completeAdvancedTutorial()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = async (evaluations: Map<string, boolean>) => {
    setIsSubmitting(true)

    const evaluationItems: EvaluationItem[] = Array.from(evaluations.entries()).map(
      ([id, isAccepted]) => ({
        id,
        is_accepted: isAccepted,
      }),
    )

    try {
      const evaluationData: EvaluationRequest = { evaluations: evaluationItems }
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
        } else if (nextPoliticianHref) {
          router.push(nextPoliticianHref)
        }
      }
    } catch (error) {
      console.error('Submission failed:', error)
      alert('Error submitting evaluations. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Session mode footer
  const sessionFooter = (evaluations: Map<string, boolean>) => (
    <div className="flex justify-between items-center">
      <div className="text-base text-foreground">
        Progress:{' '}
        <strong>
          {completedCount} / {sessionGoal}
        </strong>{' '}
        politicians evaluated
      </div>
      {evaluations.size === 0 ? (
        nextPoliticianHref ? (
          <Button href={nextPoliticianHref} className="px-6 py-3">
            Skip Politician
          </Button>
        ) : (
          <Button disabled className="px-6 py-3">
            Skip Politician
          </Button>
        )
      ) : (
        <Button
          onClick={() => handleSubmit(evaluations)}
          disabled={isSubmitting}
          className="px-6 py-3"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Evaluations & Next'}
        </Button>
      )}
    </div>
  )

  // Standalone mode footer
  const standaloneFooter = (evaluations: Map<string, boolean>) => (
    <div className="flex justify-end items-center">
      <Button
        onClick={() => handleSubmit(evaluations)}
        disabled={isSubmitting || evaluations.size === 0}
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
