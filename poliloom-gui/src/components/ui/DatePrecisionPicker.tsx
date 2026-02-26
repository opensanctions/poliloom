'use client'

import { Input } from '@/components/ui/Input'

export interface DatePrecisionValue {
  year: string
  month: string
  day: string
}

interface DatePrecisionPickerProps {
  value: DatePrecisionValue
  onChange: (value: DatePrecisionValue) => void
  label?: string
}

export function inferPrecision({ month, day }: DatePrecisionValue): number {
  if (!month) return 9
  if (!day) return 10
  return 11
}

export function formatWikidataDate(value: DatePrecisionValue): string {
  const effectiveMonth = value.month || '00'
  const effectiveDay = value.day || '00'
  return `+${value.year}-${effectiveMonth}-${effectiveDay}T00:00:00Z`
}

export function hasYear(value: DatePrecisionValue): boolean {
  return value.year.length > 0
}

export function DatePrecisionPicker({ value, onChange, label }: DatePrecisionPickerProps) {
  return (
    <div className="flex gap-2 items-center">
      {label && <label className="text-sm text-foreground-secondary">{label}</label>}
      <Input
        type="text"
        inputMode="numeric"
        placeholder="Year"
        value={value.year}
        onChange={(e) => onChange({ ...value, year: e.target.value })}
      />
      <Input
        type="text"
        inputMode="numeric"
        placeholder="Month"
        value={value.month}
        onChange={(e) => onChange({ ...value, month: e.target.value })}
      />
      <Input
        type="text"
        inputMode="numeric"
        placeholder="Day"
        value={value.day}
        onChange={(e) => onChange({ ...value, day: e.target.value })}
      />
    </div>
  )
}
