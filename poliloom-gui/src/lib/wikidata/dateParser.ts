import type { RestTimeValue, RestValue } from '@/types'

export interface ParsedTime {
  display: string
  year: number | null
  month: number | null
  day: number | null
  precision: number
}

/**
 * Extracts the time content from a REST value.
 * Returns null for somevalue/novalue snaks and non-time content.
 */
export function timeValue(value: RestValue): RestTimeValue | null {
  if (value.type !== 'value') return null
  const content = value.content
  if (
    typeof content === 'object' &&
    content !== null &&
    typeof (content as Record<string, unknown>).time === 'string' &&
    typeof (content as Record<string, unknown>).precision === 'number'
  ) {
    return content as RestTimeValue
  }
  return null
}

/**
 * Parses a REST time value into a precision-aware display string
 * plus parsed date components.
 *
 * @param value - REST time value (e.g., time "+2015-00-00T00:00:00Z")
 * @returns Parsed time with display string and components
 */
export function parseTimeValue(value: RestTimeValue): ParsedTime {
  // Remove the leading '+' and 'T00:00:00Z' suffix
  const cleanDate = value.time.replace(/^\+/, '').replace(/T00:00:00Z$/, '')
  const [yearStr, monthStr, dayStr] = cleanDate.split('-')

  const year = parseInt(yearStr, 10)
  const month = monthStr !== '00' ? parseInt(monthStr, 10) : null
  const day = dayStr !== '00' ? parseInt(dayStr, 10) : null

  let display: string

  if (value.precision >= 11 && month && day) {
    display = new Date(year, month - 1, day).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } else if (value.precision >= 10 && month) {
    display = new Date(year, month - 1).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
    })
  } else {
    display = year.toString()
  }

  return {
    display,
    year,
    month,
    day,
    precision: value.precision,
  }
}
