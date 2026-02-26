'use client'

import { useState } from 'react'
import { PropertyType, PropertyWithEvaluation, PropertyQualifiers } from '@/types'
import { Button } from '@/components/ui/Button'

interface AddPositionPropertyFormProps {
  onAdd: (property: PropertyWithEvaluation) => void
  onCancel: () => void
}

function buildDateQualifier(date: string, precision: number) {
  const [year, month, day] = date.split('-')
  const effectiveMonth = precision >= 10 ? month : '00'
  const effectiveDay = precision >= 11 ? day : '00'
  return {
    datavalue: {
      value: {
        time: `+${year}-${effectiveMonth}-${effectiveDay}T00:00:00Z`,
        precision,
      },
    },
  }
}

export function AddPositionPropertyForm({ onAdd, onCancel }: AddPositionPropertyFormProps) {
  const [entityId, setEntityId] = useState('')
  const [entityName, setEntityName] = useState('')
  const [startDate, setStartDate] = useState('')
  const [startPrecision, setStartPrecision] = useState(11)
  const [endDate, setEndDate] = useState('')
  const [endPrecision, setEndPrecision] = useState(11)

  const isValidQid = /^Q\d+$/.test(entityId)
  const isValid = isValidQid && entityName.trim().length > 0

  const handleSubmit = () => {
    if (!isValid) return

    const qualifiers: PropertyQualifiers = {}
    if (startDate) {
      qualifiers.P580 = [buildDateQualifier(startDate, startPrecision)]
    }
    if (endDate) {
      qualifiers.P582 = [buildDateQualifier(endDate, endPrecision)]
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

  const precisionSelect = (value: number, onChange: (v: number) => void) => (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="border border-border rounded px-2 py-1 bg-surface text-foreground"
    >
      <option value={11}>Day</option>
      <option value={10}>Month</option>
      <option value={9}>Year</option>
    </select>
  )

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="QID (e.g. Q30185)"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground w-40"
        />
        <input
          type="text"
          placeholder="Position name"
          value={entityName}
          onChange={(e) => setEntityName(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground flex-1"
        />
      </div>
      <div className="flex gap-3 items-center">
        <label className="text-sm text-foreground-secondary w-12">Start</label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground"
        />
        {precisionSelect(startPrecision, setStartPrecision)}
      </div>
      <div className="flex gap-3 items-center">
        <label className="text-sm text-foreground-secondary w-12">End</label>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground"
        />
        {precisionSelect(endPrecision, setEndPrecision)}
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
