'use client'

import { useState } from 'react'
import { PropertyType, PropertyWithEvaluation } from '@/types'
import { Button } from '@/components/ui/Button'

interface AddDatePropertyFormProps {
  onAdd: (property: PropertyWithEvaluation) => void
  onCancel: () => void
}

export function AddDatePropertyForm({ onAdd, onCancel }: AddDatePropertyFormProps) {
  const [type, setType] = useState<PropertyType.P569 | PropertyType.P570>(PropertyType.P569)
  const [date, setDate] = useState('')
  const [precision, setPrecision] = useState(11)

  const handleSubmit = () => {
    if (!date) return

    // Parse the date input and format to Wikidata format
    // Zero out components below the chosen precision
    const [year, month, day] = date.split('-')
    const effectiveMonth = precision >= 10 ? month : '00'
    const effectiveDay = precision >= 11 ? day : '00'
    const wikidataValue = `+${year}-${effectiveMonth}-${effectiveDay}T00:00:00Z`

    const property: PropertyWithEvaluation = {
      key: `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      type,
      value: wikidataValue,
      value_precision: precision,
      statement_id: null,
      sources: [],
      evaluation: true,
    }

    onAdd(property)
  }

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex gap-3">
        <select
          value={type}
          onChange={(e) => setType(e.target.value as PropertyType.P569 | PropertyType.P570)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground"
        >
          <option value={PropertyType.P569}>Birth Date</option>
          <option value={PropertyType.P570}>Death Date</option>
        </select>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground"
        />
        <select
          value={precision}
          onChange={(e) => setPrecision(Number(e.target.value))}
          className="border border-border rounded px-2 py-1 bg-surface text-foreground"
        >
          <option value={11}>Day</option>
          <option value={10}>Month</option>
          <option value={9}>Year</option>
        </select>
      </div>
      <div className="flex gap-2">
        <Button size="small" onClick={handleSubmit} disabled={!date}>
          Add
        </Button>
        <Button size="small" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
