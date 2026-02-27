'use client'

import { useState } from 'react'
import { PropertyType, CreatePropertyItem } from '@/types'
import { Button } from '@/components/ui/Button'
import { EntitySearch } from '@/components/ui/EntitySearch'

interface AddEntityPropertyFormProps {
  type: PropertyType.P19 | PropertyType.P27
  onAdd: (property: CreatePropertyItem) => void
  onCancel: () => void
}

const SEARCH_ENDPOINTS: Record<PropertyType.P19 | PropertyType.P27, string> = {
  [PropertyType.P19]: '/api/locations/search',
  [PropertyType.P27]: '/api/countries/search',
}

const PLACEHOLDERS: Record<PropertyType.P19 | PropertyType.P27, string> = {
  [PropertyType.P19]: 'Search for a location...',
  [PropertyType.P27]: 'Search for a country...',
}

export function AddEntityPropertyForm({ type, onAdd, onCancel }: AddEntityPropertyFormProps) {
  const [selectedEntity, setSelectedEntity] = useState<{
    wikidata_id: string
    name: string
  } | null>(null)

  const handleSubmit = () => {
    if (!selectedEntity) return

    const property: CreatePropertyItem = {
      action: 'create',
      key: `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      type,
      entity_id: selectedEntity.wikidata_id,
      entity_name: selectedEntity.name,
    }

    onAdd(property)
  }

  return (
    <div className="border border-border rounded-lg px-6 py-5 space-y-3">
      <EntitySearch
        searchEndpoint={SEARCH_ENDPOINTS[type]}
        onSelect={setSelectedEntity}
        onClear={() => setSelectedEntity(null)}
        selectedEntity={selectedEntity}
        placeholder={PLACEHOLDERS[type]}
      />
      <div className="flex gap-2">
        <Button size="small" onClick={handleSubmit} disabled={!selectedEntity}>
          + Add
        </Button>
        <Button size="small" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
