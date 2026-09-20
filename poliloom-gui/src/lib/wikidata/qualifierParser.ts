import type { RestSnak } from '@/types'
import { parseTimeValue, timeValue, type ParsedTime } from './dateParser'

export interface Timeframe {
  start: ParsedTime | null
  end: ParsedTime | null
}

/**
 * Returns the qualifiers with the given property id.
 */
export function findQualifiers(qualifiers: RestSnak[], propertyId: string): RestSnak[] {
  return qualifiers.filter((snak) => snak.property.id === propertyId)
}

/**
 * Compares two parsed times for sorting purposes.
 * Returns negative if a < b, positive if a > b, 0 if equal.
 */
export function compareTimes(a: ParsedTime, b: ParsedTime): number {
  if (a.year !== b.year) return (a.year ?? 0) - (b.year ?? 0)
  if (a.month !== b.month) return (a.month ?? 0) - (b.month ?? 0)
  if (a.day !== b.day) return (a.day ?? 0) - (b.day ?? 0)
  return 0
}

/**
 * Selects the best time from multiple qualifier snaks.
 *
 * Some positions have multiple P580/P582 values (e.g., Q547153 held "delegate"
 * across 9 terms). Wikidata recommends a single "best" value marked with
 * preferred rank, so we select one representative date rather than displaying
 * all values.
 *
 * Strategy: prefer the most precise date (precision 11 > 10 > 9), then the
 * earliest for start dates or the latest for end dates.
 */
function selectBestTime(snaks: RestSnak[], preferLatest: boolean): ParsedTime | null {
  const parsedTimes: ParsedTime[] = []

  for (const snak of snaks) {
    const time = timeValue(snak.value)
    if (time) parsedTimes.push(parseTimeValue(time))
  }

  if (parsedTimes.length === 0) return null
  if (parsedTimes.length === 1) return parsedTimes[0]

  // Sort by precision (descending - higher is more precise), then by time
  parsedTimes.sort((a, b) => {
    if (a.precision !== b.precision) {
      return b.precision - a.precision
    }
    const timeComparison = compareTimes(a, b)
    return preferLatest ? -timeComparison : timeComparison
  })

  return parsedTimes[0]
}

/**
 * Extracts a statement timeframe from REST qualifiers: P580 (start time) and
 * P582 (end time). When multiple values exist for either, selects the best
 * one: most precise first, then earliest for starts and latest for ends.
 */
export function parseTimeframe(qualifiers: RestSnak[]): Timeframe {
  return {
    start: selectBestTime(findQualifiers(qualifiers, 'P580'), false),
    end: selectBestTime(findQualifiers(qualifiers, 'P582'), true),
  }
}

/**
 * Formats a timeframe for display.
 *
 * @param timeframe - Parsed timeframe
 * @returns Human-readable date range string
 */
export function formatTimeframe(timeframe: Timeframe): string {
  const { start, end } = timeframe

  if (!start && !end) {
    return 'dates not specified'
  }

  if (start && end) {
    return `${start.display} – ${end.display}`
  }

  if (start) {
    return `${start.display} – present`
  }

  return `until ${end!.display}`
}
