'use client'

import { useState } from 'react'
import { Politician, EvaluationItem } from '@/types'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { Button } from './Button'
import { PoliticianEvaluationView } from './PoliticianEvaluationView'

interface PoliticianEvaluationProps {
  politician: Politician
}

export function PoliticianEvaluation({ politician }: PoliticianEvaluationProps) {
  const { completedCount, sessionGoal, submitEvaluation, skipPolitician } = useEvaluationSession()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (evaluations: Map<string, boolean>) => {
    // If no evaluations, just skip to the next politician (doesn't count toward session)
    if (evaluations.size === 0) {
      skipPolitician()
      return
    }

    setIsSubmitting(true)

    const evaluationItems: EvaluationItem[] = Array.from(evaluations.entries()).map(
      ([id, isAccepted]) => ({
        id,
        is_accepted: isAccepted,
      }),
    )

    try {
      // Submit evaluation - context handles all errors, incrementing, advancing, and navigation
      await submitEvaluation(evaluationItems)
    } catch (error) {
      // Error already handled by context - just preserve evaluation state
      console.error('Submission failed:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <PoliticianEvaluationView
      politician={politician}
      footer={({ evaluations }) => (
        <div className="flex justify-between items-center">
          <div className="text-base text-gray-900">
            Progress:{' '}
            <strong>
              {completedCount} / {sessionGoal}
            </strong>{' '}
            politicians evaluated
          </div>
          <Button
            onClick={() => handleSubmit(evaluations)}
            disabled={isSubmitting}
            className="px-6 py-3"
          >
            {isSubmitting
              ? 'Submitting...'
              : evaluations.size === 0
                ? 'Skip Politician'
                : 'Submit Evaluations & Next'}
          </Button>
        </div>
      )}
    />
  )
}
