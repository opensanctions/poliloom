'use client'

import { useState } from 'react'
import { PropertyType, PropertyWithEvaluation } from '@/types'
import { Button } from '@/components/ui/Button'

interface AddEntityPropertyFormProps {
  type: PropertyType.P19 | PropertyType.P27
  onAdd: (property: PropertyWithEvaluation) => void
  onCancel: () => void
}

export function AddEntityPropertyForm({ type, onAdd, onCancel }: AddEntityPropertyFormProps) {
  const [entityId, setEntityId] = useState('')
  const [entityName, setEntityName] = useState('')

  const isValidQid = /^Q\d+$/.test(entityId)
  const isValid = isValidQid && entityName.trim().length > 0

  const handleSubmit = () => {
    if (!isValid) return

    const property: PropertyWithEvaluation = {
      key: `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      type,
      entity_id: entityId,
      entity_name: entityName.trim(),
      statement_id: null,
      sources: [],
      evaluation: true,
    }

    onAdd(property)
  }

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="QID (e.g. Q64)"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground w-32"
        />
        <input
          type="text"
          placeholder="Name"
          value={entityName}
          onChange={(e) => setEntityName(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground flex-1"
        />
      </div>
      <div className="flex gap-2">
        <Button size="small" onClick={handleSubmit} disabled={!isValid}>
          Add
        </Button>
        <Button size="small" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
