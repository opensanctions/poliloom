import { parseWikidataDate, ParsedWikidataDate } from './dateParser';

export interface ParsedPositionDates {
  startDate: ParsedWikidataDate | null;
  endDate: ParsedWikidataDate | null;
}

interface WikidataSnak {
  datavalue?: {
    value?: {
      time?: string;
      precision?: number;
    };
  };
}

/**
 * Extracts position start and end dates from Wikidata qualifiers
 *
 * @param qualifiers - Record containing qualifier data with P580 (start) and P582 (end) properties
 * @returns Parsed start and end dates, or null if not found
 */
export function parsePositionQualifiers(qualifiers: Record<string, any>): ParsedPositionDates {
  let startDate: ParsedWikidataDate | null = null;
  let endDate: ParsedWikidataDate | null = null;

  // Extract P580 (start date)
  if (qualifiers.P580) {
    const startQualifier = qualifiers.P580;
    if (Array.isArray(startQualifier) && startQualifier.length > 0) {
      const snak = startQualifier[0] as WikidataSnak;
      if (snak.datavalue?.value?.time && snak.datavalue?.value?.precision) {
        startDate = parseWikidataDate(
          snak.datavalue.value.time,
          snak.datavalue.value.precision
        );
      }
    }
  }

  // Extract P582 (end date)
  if (qualifiers.P582) {
    const endQualifier = qualifiers.P582;
    if (Array.isArray(endQualifier) && endQualifier.length > 0) {
      const snak = endQualifier[0] as WikidataSnak;
      if (snak.datavalue?.value?.time && snak.datavalue?.value?.precision) {
        endDate = parseWikidataDate(
          snak.datavalue.value.time,
          snak.datavalue.value.precision
        );
      }
    }
  }

  return { startDate, endDate };
}

/**
 * Formats position dates for display
 *
 * @param dates - Parsed position dates
 * @returns Human-readable date range string
 */
export function formatPositionDates(dates: ParsedPositionDates): string {
  const { startDate, endDate } = dates;

  if (!startDate && !endDate) {
    return '';
  }

  if (startDate && endDate) {
    return `${startDate.display} – ${endDate.display}`;
  }

  if (startDate) {
    return `${startDate.display} – present`;
  }

  if (endDate) {
    return `until ${endDate.display}`;
  }

  return '';
}