'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Politician,
  CreatePoliticianRequest,
  CreatePoliticianResponse,
  CreatePropertyItem,
  PropertyActionItem,
} from '@/types'
import { Button } from '@/components/ui/Button'
import { EvaluationView } from '@/components/evaluation/EvaluationView'

export default function CreatePoliticianPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Stable synthetic politician with a client-generated ID
  const [syntheticId] = useState(() => crypto.randomUUID())
  const syntheticPolitician: Politician = {
    id: syntheticId,
    name: name || 'New Politician',
    wikidata_id: null,
    properties: [],
  }

  const handleSubmit = async (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    const actions = actionsByPolitician.get(syntheticId) || []
    const createItems = actions.filter((a): a is CreatePropertyItem => a.action === 'create')

    if (!name.trim()) {
      alert('Please enter a name for the politician.')
      return
    }

    if (createItems.length === 0) {
      alert('Please add at least one property.')
      return
    }

    setIsSubmitting(true)

    try {
      const requestData: CreatePoliticianRequest = {
        name: name.trim(),
        items: createItems,
      }

      const response = await fetch('/api/politicians', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData),
      })

      if (!response.ok) {
        throw new Error(`Failed to create politician: ${response.statusText}`)
      }

      const result: CreatePoliticianResponse = await response.json()
      if (!result.success) {
        console.error('Creation errors:', result.errors)
        alert(`Error creating politician: ${result.message}`)
        return
      }

      if (result.wikidata_id) {
        router.push(`/politician/${result.wikidata_id}`)
      }
    } catch (error) {
      console.error('Creation failed:', error)
      alert('Error creating politician. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const footer = (actionsByPolitician: Map<string, PropertyActionItem[]>) => {
    const actions = actionsByPolitician.get(syntheticId) || []
    const hasCreateActions = actions.some((a) => a.action === 'create')

    return (
      <div className="flex items-center gap-4">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Politician name"
          className="flex-1 px-4 py-2 border border-border rounded-lg bg-background text-foreground text-lg"
        />
        <Button
          onClick={() => handleSubmit(actionsByPolitician)}
          disabled={isSubmitting || !name.trim() || !hasCreateActions}
          className="px-6 py-3"
        >
          {isSubmitting ? 'Creating...' : 'Create Politician'}
        </Button>
      </div>
    )
  }

  return <EvaluationView politicians={[syntheticPolitician]} footer={footer} />
}
