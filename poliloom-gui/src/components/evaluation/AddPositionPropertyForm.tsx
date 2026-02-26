'use client'

import { useState } from 'react'
import { PropertyType, PropertyWithEvaluation, PropertyQualifiers } from '@/types'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import {
  DatePrecisionPicker,
  DatePrecisionValue,
  formatWikidataDate,
  inferPrecision,
  hasYear,
} from '@/components/ui/DatePrecisionPicker'

interface AddPositionPropertyFormProps {
  onAdd: (property: PropertyWithEvaluation) => void
  onCancel: () => void
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

export function AddPositionPropertyForm({ onAdd, onCancel }: AddPositionPropertyFormProps) {
  const [entityId, setEntityId] = useState('')
  const [entityName, setEntityName] = useState('')
  const [startDate, setStartDate] = useState<DatePrecisionValue>(emptyDate)
  const [endDate, setEndDate] = useState<DatePrecisionValue>(emptyDate)

  const isValidQid = /^Q\d+$/.test(entityId)
  const isValid = isValidQid && entityName.trim().length > 0

  const handleSubmit = () => {
    if (!isValid) return

    const qualifiers: PropertyQualifiers = {}
    if (hasYear(startDate)) {
      qualifiers.P580 = [buildDateQualifier(startDate)]
    }
    if (hasYear(endDate)) {
      qualifiers.P582 = [buildDateQualifier(endDate)]
    }

    const property: PropertyWithEvaluation = {
      key: `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      type: PropertyType.P39,
      entity_id: entityId,
      entity_name: entityName.trim(),
      qualifiers: Object.keys(qualifiers).length > 0 ? qualifiers : undefined,
      statement_id: null,
      sources: [],
      evaluation: true,
    }

    onAdd(property)
  }

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex gap-3">
        <Input
          placeholder="QID (e.g. Q30185)"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
        />
        <Input
          placeholder="Position name"
          value={entityName}
          onChange={(e) => setEntityName(e.target.value)}
        />
      </div>
      <DatePrecisionPicker label="Start" value={startDate} onChange={setStartDate} />
      <DatePrecisionPicker label="End" value={endDate} onChange={setEndDate} />
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
