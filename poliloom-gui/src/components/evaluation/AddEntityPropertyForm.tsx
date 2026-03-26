'use client'

import { useState } from 'react'
import {
  PropertyType,
  EntityPropertyType,
  CreatePropertyItem,
  PropertyQualifiers,
  SearchFn,
} from '@/types'
import { Button } from '@/components/ui/Button'
import { EntitySelector } from '@/components/ui/EntitySelector'
import {
  DatePrecisionPicker,
  DatePrecisionValue,
  formatWikidataDate,
  inferPrecision,
  hasYear,
} from '@/components/ui/DatePrecisionPicker'

const PLACEHOLDERS: Record<EntityPropertyType, string> = {
  [PropertyType.P19]: 'Search for a location...',
  [PropertyType.P27]: 'Search for a country...',
  [PropertyType.P39]: 'Search for a position...',
}

function entitySearch(searchType: string): SearchFn {
  return async (q) => {
    const res = await fetch(`/api/entities/search?type=${searchType}&q=${encodeURIComponent(q)}`)
    if (!res.ok) throw new Error('Search failed')
    return res.json()
  }
}

const DEFAULT_ENTITY_SEARCHES: Record<EntityPropertyType, SearchFn> = {
  [PropertyType.P19]: entitySearch('location'),
  [PropertyType.P27]: entitySearch('country'),
  [PropertyType.P39]: entitySearch('position'),
}

interface AddEntityPropertyFormProps {
  type: EntityPropertyType
  onAdd: (property: CreatePropertyItem) => void
  onCancel: () => void
  onSearch?: SearchFn
}

function buildDateQualifier(date: DatePrecisionValue) {
  return {
    datavalue: {
      value: {
        time: formatWikidataDate(date),
        precision: inferPrecision(date),
      },
    },
  }
}

const emptyDate: DatePrecisionValue = { year: '', month: '', day: '' }

export function AddEntityPropertyForm({
  type,
  onAdd,
  onCancel,
  onSearch,
}: AddEntityPropertyFormProps) {
  const search = onSearch ?? DEFAULT_ENTITY_SEARCHES[type]
  const showDates = type === PropertyType.P39

  const [selectedEntity, setSelectedEntity] = useState<{
    wikidata_id: string
    name: string
  } | null>(null)
  const [startDate, setStartDate] = useState<DatePrecisionValue>(emptyDate)
  const [endDate, setEndDate] = useState<DatePrecisionValue>(emptyDate)

  const handleSubmit = () => {
    if (!selectedEntity) return

    const qualifiers: PropertyQualifiers = {}
    if (showDates) {
      if (hasYear(startDate)) {
        qualifiers.P580 = [buildDateQualifier(startDate)]
      }
      if (hasYear(endDate)) {
        qualifiers.P582 = [buildDateQualifier(endDate)]
      }
    }

    onAdd({
      action: 'create',
      id: crypto.randomUUID(),
      type,
      entity_id: selectedEntity.wikidata_id,
      entity_name: selectedEntity.name,
      qualifiers: Object.keys(qualifiers).length > 0 ? qualifiers : undefined,
    })
  }

  return (
    <div className="border border-border rounded-lg px-6 py-5 space-y-3">
      <EntitySelector
        onSearch={search}
        onSelect={setSelectedEntity}
        onClear={() => setSelectedEntity(null)}
        selectedEntity={selectedEntity}
        placeholder={PLACEHOLDERS[type]}
      />
      {showDates && (
        <>
          <DatePrecisionPicker label="Start" value={startDate} onChange={setStartDate} />
          <DatePrecisionPicker label="End" value={endDate} onChange={setEndDate} />
        </>
      )}
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
