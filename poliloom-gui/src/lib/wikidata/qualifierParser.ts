import { parseWikidataDate, ParsedWikidataDate } from './dateParser'

export interface ParsedPositionDates {
  startDate: ParsedWikidataDate | null
  endDate: ParsedWikidataDate | null
}

interface WikidataSnak {
  datavalue?: {
    value?: {
      time?: string
      precision?: number
    }
  }
}

/**
 * Compares two parsed dates for sorting purposes.
 * Returns negative if a < b, positive if a > b, 0 if equal.
 */
export function compareDates(a: ParsedWikidataDate, b: ParsedWikidataDate): number {
  if (a.year !== b.year) return (a.year ?? 0) - (b.year ?? 0)
  if (a.month !== b.month) return (a.month ?? 0) - (b.month ?? 0)
  if (a.day !== b.day) return (a.day ?? 0) - (b.day ?? 0)
  return 0
}

/**
 * Selects the best date from multiple qualifier values.
 *
 * Some positions have multiple P580/P582 values (e.g., Q547153 held "delegate" across 9 terms).
 * Wikidata recommends a single "best" value marked with preferred rank, so we select one
 * representative date rather than displaying all values.
 *
 * Strategy: prefer most precise date (precision 11 > 10 > 9), then earliest for start dates
 * or latest for end dates.
 *
 * @param snaks - Array of qualifier snaks
 * @param preferLatest - If true, prefer later dates when precision is equal (for end dates)
 */
function selectBestDate(
  snaks: WikidataSnak[],
  preferLatest: boolean = false,
): ParsedWikidataDate | null {
  const parsedDates: ParsedWikidataDate[] = []

  for (const snak of snaks) {
    if (snak.datavalue?.value?.time && snak.datavalue?.value?.precision) {
      parsedDates.push(parseWikidataDate(snak.datavalue.value.time, snak.datavalue.value.precision))
    }
  }

  if (parsedDates.length === 0) return null
  if (parsedDates.length === 1) return parsedDates[0]

  // Sort by precision (descending - higher is more precise), then by date
  parsedDates.sort((a, b) => {
    // First compare by precision (higher precision wins)
    if (a.precision !== b.precision) {
      return b.precision - a.precision
    }
    // If same precision, compare by date value
    const dateComparison = compareDates(a, b)
    return preferLatest ? -dateComparison : dateComparison
  })

  return parsedDates[0]
}

/**
 * Extracts position start and end dates from Wikidata qualifiers.
 * When multiple dates exist for P580 or P582, selects the best date using:
 * - Most precise date (day > month > year)
 * - For P580 (start): earliest date when precision is equal
 * - For P582 (end): latest date when precision is equal
 *
 * @param qualifiers - Record containing qualifier data with P580 (start) and P582 (end) properties
 * @returns Parsed start and end dates, or null if not found
 */
export function parsePositionQualifiers(qualifiers: Record<string, unknown>): ParsedPositionDates {
  let startDate: ParsedWikidataDate | null = null
  let endDate: ParsedWikidataDate | null = null

  // Extract P580 (start date) - prefer most precise, then earliest
  if (qualifiers.P580) {
    const startQualifier = qualifiers.P580
    if (Array.isArray(startQualifier) && startQualifier.length > 0) {
      startDate = selectBestDate(startQualifier as WikidataSnak[], false)
    }
  }

  // Extract P582 (end date) - prefer most precise, then latest
  if (qualifiers.P582) {
    const endQualifier = qualifiers.P582
    if (Array.isArray(endQualifier) && endQualifier.length > 0) {
      endDate = selectBestDate(endQualifier as WikidataSnak[], true)
    }
  }

  return { startDate, endDate }
}

/**
 * Formats position dates for display
 *
 * @param dates - Parsed position dates
 * @returns Human-readable date range string
 */
export function formatPositionDates(dates: ParsedPositionDates): string {
  const { startDate, endDate } = dates

  if (!startDate && !endDate) {
    return 'dates not specified'
  }

  if (startDate && endDate) {
    return `${startDate.display} – ${endDate.display}`
  }

  if (startDate) {
    return `${startDate.display} – present`
  }

  if (endDate) {
    return `until ${endDate.display}`
  }

  return ''
}
