'use client'

import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useMemo } from 'react'

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

const MONTH_OPTIONS = [
  { value: '01', label: 'January' },
  { value: '02', label: 'February' },
  { value: '03', label: 'March' },
  { value: '04', label: 'April' },
  { value: '05', label: 'May' },
  { value: '06', label: 'June' },
  { value: '07', label: 'July' },
  { value: '08', label: 'August' },
  { value: '09', label: 'September' },
  { value: '10', label: 'October' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
]

function getDaysInMonth(year: string, month: string): number {
  if (!year || !month) return 31
  return new Date(parseInt(year), parseInt(month), 0).getDate()
}

export function DatePrecisionPicker({ value, onChange, label }: DatePrecisionPickerProps) {
  const daysInMonth = getDaysInMonth(value.year, value.month)

  const dayOptions = useMemo(
    () =>
      Array.from({ length: daysInMonth }, (_, i) => ({
        value: String(i + 1).padStart(2, '0'),
        label: String(i + 1),
      })),
    [daysInMonth],
  )

  return (
    <div className="flex gap-2 items-center">
      {label && <label className="text-sm text-foreground-secondary w-10 shrink-0">{label}</label>}
      <Input
        type="number"
        placeholder="Year"
        value={value.year}
        onChange={(e) => onChange({ ...value, year: e.target.value })}
        className="w-24"
      />
      <Select
        options={MONTH_OPTIONS}
        value={value.month}
        placeholder="Month"
        onChange={(newMonth) => {
          const newDays = getDaysInMonth(value.year, newMonth)
          const adjustedDay =
            value.day && parseInt(value.day) > newDays
              ? String(newDays).padStart(2, '0')
              : value.day
          onChange({ ...value, month: newMonth, day: newMonth ? adjustedDay : '' })
        }}
      />
      <Select
        options={dayOptions}
        value={value.month ? value.day : ''}
        placeholder="Day"
        onChange={(newDay) => onChange({ ...value, day: newDay })}
        disabled={!value.month}
      />
    </div>
  )
}
