export interface ParsedWikidataDate {
  display: string
  year: number | null
  month: number | null
  day: number | null
  precision: number
}

/**
 * Parses Wikidata date strings and returns a human-readable display string
 * along with parsed date components.
 *
 * @param dateString - Wikidata date string (e.g., "+2015-00-00T00:00:00Z")
 * @param precision - Precision level (9=year, 10=month, 11=day)
 * @returns Parsed date with display string and components
 */
export function parseWikidataDate(dateString: string, precision: number): ParsedWikidataDate {
  // Remove the leading '+' and 'T00:00:00Z' suffix
  const cleanDate = dateString.replace(/^\+/, '').replace(/T00:00:00Z$/, '')
  const [yearStr, monthStr, dayStr] = cleanDate.split('-')

  const year = parseInt(yearStr, 10)
  const month = monthStr !== '00' ? parseInt(monthStr, 10) : null
  const day = dayStr !== '00' ? parseInt(dayStr, 10) : null

  let display: string

  if (precision >= 11 && month && day) {
    display = new Date(year, month - 1, day).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } else if (precision >= 10 && month) {
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
    precision,
  }
}
