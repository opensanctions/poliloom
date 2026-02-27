'use client'

import { useState } from 'react'
import { PropertyType, CreatePropertyItem } from '@/types'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import {
  DatePrecisionPicker,
  DatePrecisionValue,
  formatWikidataDate,
  inferPrecision,
  hasYear,
} from '@/components/ui/DatePrecisionPicker'

interface AddDatePropertyFormProps {
  onAdd: (property: CreatePropertyItem) => void
  onCancel: () => void
}

export function AddDatePropertyForm({ onAdd, onCancel }: AddDatePropertyFormProps) {
  const [type, setType] = useState<PropertyType.P569 | PropertyType.P570>(PropertyType.P569)
  const [date, setDate] = useState<DatePrecisionValue>({ year: '', month: '', day: '' })

  const handleSubmit = () => {
    if (!hasYear(date)) return

    const property: CreatePropertyItem = {
      action: 'create',
      key: `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      type,
      value: formatWikidataDate(date),
      value_precision: inferPrecision(date),
    }

    onAdd(property)
  }

  return (
    <div className="border border-border rounded-lg px-6 py-5 space-y-3">
      <Select
        options={[
          { value: PropertyType.P569, label: 'Birth Date' },
          { value: PropertyType.P570, label: 'Death Date' },
        ]}
        value={type}
        onChange={(v) => setType(v as PropertyType.P569 | PropertyType.P570)}
      />
      <DatePrecisionPicker value={date} onChange={setDate} />
      <div className="flex gap-2">
        <Button size="small" onClick={handleSubmit} disabled={!hasYear(date)}>
          + Add
        </Button>
        <Button size="small" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
