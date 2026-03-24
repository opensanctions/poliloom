'use client'

import { useParams } from 'next/navigation'
import {
  Politician,
  SourcePatchPropertiesRequest,
  PatchPropertiesResponse,
  PropertyActionItem,
} from '@/types'
import { Button } from '@/components/ui/Button'
import { EvaluationView, FooterContext } from '@/components/evaluation/EvaluationView'

interface SourceEvaluationProps {
  politicians: Politician[]
}

export function SourceEvaluation({ politicians }: SourceEvaluationProps) {
  const { id } = useParams<{ id: string }>()

  const handleSubmit = async (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    const items: Record<string, PropertyActionItem[]> = {}

    for (const [id, actions] of actionsByPolitician) {
      if (actions.length > 0) {
        items[id] = actions
      }
    }

    const requestData: SourcePatchPropertiesRequest = { items }
    const response = await fetch(`/api/sources/${id}`, {
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
  }

  const hasChanges = (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    for (const actions of actionsByPolitician.values()) {
      if (actions.length > 0) return true
    }
    return false
  }

  const footer = ({ actionsByPolitician, isSubmitting, submit }: FooterContext) => (
    <div className="flex justify-end items-center">
      <Button
        onClick={submit}
        disabled={isSubmitting || !hasChanges(actionsByPolitician)}
        className="px-6 py-3"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Evaluations'}
      </Button>
    </div>
  )

  return <EvaluationView politicians={politicians} onSubmit={handleSubmit} footer={footer} />
}
