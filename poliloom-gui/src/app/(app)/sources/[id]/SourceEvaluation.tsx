'use client'

import { useState } from 'react'
import {
  SourceResponse,
  PropertyWithEvaluation,
  SourcePatchPropertiesRequest,
  PatchPropertiesResponse,
  PropertyActionItem,
} from '@/types'
import { Button } from '@/components/ui/Button'
import { SourceEvaluationView } from '@/components/evaluation/SourceEvaluationView'

interface SourceEvaluationProps {
  source: SourceResponse
}

export function SourceEvaluation({ source }: SourceEvaluationProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (propertiesByPolitician: Map<string, PropertyWithEvaluation[]>) => {
    setIsSubmitting(true)

    // Build items keyed by politician QID
    const items: Record<string, PropertyActionItem[]> = {}

    for (const [qid, properties] of propertiesByPolitician) {
      const politicianItems: PropertyActionItem[] = properties
        .filter((p) => p.evaluation !== undefined || !p.id)
        .map((p): PropertyActionItem => {
          if (p.id) {
            return {
              action: p.evaluation ? 'accept' : 'reject',
              id: p.id,
            }
          }
          return {
            action: 'create',
            type: p.type,
            value: p.value,
            value_precision: p.value_precision,
            entity_id: p.entity_id,
            qualifiers_json: p.qualifiers as Record<string, unknown> | undefined,
          }
        })

      if (politicianItems.length > 0) {
        items[qid] = politicianItems
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

  const hasChanges = (propertiesByPolitician: Map<string, PropertyWithEvaluation[]>) => {
    for (const properties of propertiesByPolitician.values()) {
      if (properties.some((p) => p.evaluation !== undefined || !p.id)) {
        return true
      }
    }
    return false
  }

  const footer = (propertiesByPolitician: Map<string, PropertyWithEvaluation[]>) => (
    <div className="flex justify-end items-center">
      <Button
        onClick={() => handleSubmit(propertiesByPolitician)}
        disabled={isSubmitting || !hasChanges(propertiesByPolitician)}
        className="px-6 py-3"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Evaluations'}
      </Button>
    </div>
  )

  return <SourceEvaluationView source={source} footer={footer} />
}
