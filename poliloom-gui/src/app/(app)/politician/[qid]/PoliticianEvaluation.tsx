'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Politician,
  PatchPropertiesRequest,
  PatchPropertiesResponse,
  PropertyActionItem,
} from '@/types'
import { stripCreateKeys } from '@/lib/evaluation'
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

  const handleSubmit = async (actions: PropertyActionItem[]) => {
    setIsSubmitting(true)

    try {
      const requestData: PatchPropertiesRequest = { items: stripCreateKeys(actions) }
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

  // Session mode footer
  const sessionFooter = (actions: PropertyActionItem[]) => (
    <div className="flex justify-between items-center">
      <div className="text-base text-foreground">
        Progress:{' '}
        <strong>
          {completedCount} / {sessionGoal}
        </strong>{' '}
        politicians evaluated
      </div>
      {actions.length === 0 ? (
        <Button
          href={nextPoliticianHref ?? (nextLoading ? undefined : '/session/enriching')}
          disabled={nextLoading}
          className="px-6 py-3"
        >
          Skip Politician
        </Button>
      ) : (
        <Button
          onClick={() => handleSubmit(actions)}
          disabled={isSubmitting || nextLoading}
          className="px-6 py-3"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Evaluations & Next'}
        </Button>
      )}
    </div>
  )

  // Standalone mode footer
  const standaloneFooter = (actions: PropertyActionItem[]) => (
    <div className="flex justify-end items-center">
      <Button
        onClick={() => handleSubmit(actions)}
        disabled={isSubmitting || actions.length === 0}
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
