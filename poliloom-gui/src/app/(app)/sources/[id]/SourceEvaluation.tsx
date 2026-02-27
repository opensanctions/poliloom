'use client'

import { useState } from 'react'
import {
  SourceResponse,
  SourcePatchPropertiesRequest,
  PatchPropertiesResponse,
  PropertyActionItem,
} from '@/types'
import { stripCreateKeys } from '@/lib/evaluation'
import { Button } from '@/components/ui/Button'
import { SourceEvaluationView } from '@/components/evaluation/SourceEvaluationView'

interface SourceEvaluationProps {
  source: SourceResponse
}

export function SourceEvaluation({ source }: SourceEvaluationProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    setIsSubmitting(true)

    const items: Record<string, PropertyActionItem[]> = {}

    for (const [qid, actions] of actionsByPolitician) {
      if (actions.length > 0) {
        items[qid] = stripCreateKeys(actions)
      }
    }

    try {
      const requestData: SourcePatchPropertiesRequest = { items }
      const response = await fetch(`/api/sources/${source.archived_page.id}`, {
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
    } catch (error) {
      console.error('Submission failed:', error)
      alert('Error submitting evaluations. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const hasChanges = (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    for (const actions of actionsByPolitician.values()) {
      if (actions.length > 0) return true
    }
    return false
  }

  const footer = (actionsByPolitician: Map<string, PropertyActionItem[]>) => (
    <div className="flex justify-end items-center">
      <Button
        onClick={() => handleSubmit(actionsByPolitician)}
        disabled={isSubmitting || !hasChanges(actionsByPolitician)}
        className="px-6 py-3"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Evaluations'}
      </Button>
    </div>
  )

  return <SourceEvaluationView source={source} footer={footer} />
}
