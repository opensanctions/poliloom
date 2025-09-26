export interface ParsedWikidataDate {
  display: string;
  year: number | null;
  month: number | null;
  day: number | null;
  precision: number;
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
  const cleanDate = dateString.replace(/^\+/, '').replace(/T00:00:00Z$/, '');
  const [yearStr, monthStr, dayStr] = cleanDate.split('-');

  const year = parseInt(yearStr, 10);
  const month = monthStr !== '00' ? parseInt(monthStr, 10) : null;
  const day = dayStr !== '00' ? parseInt(dayStr, 10) : null;

  let display: string;

  switch (precision) {
    case 9: // Year only
      display = year.toString();
      break;
    case 10: // Month and year
      if (month) {
        const monthNames = [
          'January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December'
        ];
        display = `${monthNames[month - 1]} ${year}`;
      } else {
        display = year.toString();
      }
      break;
    case 11: // Full date
      if (month && day) {
        const monthNames = [
          'January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December'
        ];
        display = `${monthNames[month - 1]} ${day}, ${year}`;
      } else if (month) {
        const monthNames = [
          'January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December'
        ];
        display = `${monthNames[month - 1]} ${year}`;
      } else {
        display = year.toString();
      }
      break;
    default:
      display = year.toString();
  }

  return {
    display,
    year,
    month,
    day,
    precision
  };
}