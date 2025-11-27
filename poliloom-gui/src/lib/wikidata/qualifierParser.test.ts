import { describe, it, expect } from 'vitest'
import { parsePositionQualifiers, compareDates } from './qualifierParser'
import { ParsedWikidataDate } from './dateParser'

describe('compareDates', () => {
  it('returns negative when first date is earlier', () => {
    const a: ParsedWikidataDate = {
      display: '1990',
      year: 1990,
      month: null,
      day: null,
      precision: 9,
    }
    const b: ParsedWikidataDate = {
      display: '2000',
      year: 2000,
      month: null,
      day: null,
      precision: 9,
    }
    expect(compareDates(a, b)).toBeLessThan(0)
  })

  it('returns positive when first date is later', () => {
    const a: ParsedWikidataDate = {
      display: '2000',
      year: 2000,
      month: null,
      day: null,
      precision: 9,
    }
    const b: ParsedWikidataDate = {
      display: '1990',
      year: 1990,
      month: null,
      day: null,
      precision: 9,
    }
    expect(compareDates(a, b)).toBeGreaterThan(0)
  })

  it('returns 0 for equal dates', () => {
    const a: ParsedWikidataDate = {
      display: 'January 1, 2000',
      year: 2000,
      month: 1,
      day: 1,
      precision: 11,
    }
    const b: ParsedWikidataDate = {
      display: 'January 1, 2000',
      year: 2000,
      month: 1,
      day: 1,
      precision: 11,
    }
    expect(compareDates(a, b)).toBe(0)
  })

  it('compares by month when years are equal', () => {
    const a: ParsedWikidataDate = {
      display: 'January 2000',
      year: 2000,
      month: 1,
      day: null,
      precision: 10,
    }
    const b: ParsedWikidataDate = {
      display: 'March 2000',
      year: 2000,
      month: 3,
      day: null,
      precision: 10,
    }
    expect(compareDates(a, b)).toBeLessThan(0)
  })

  it('compares by day when year and month are equal', () => {
    const a: ParsedWikidataDate = {
      display: 'January 1, 2000',
      year: 2000,
      month: 1,
      day: 1,
      precision: 11,
    }
    const b: ParsedWikidataDate = {
      display: 'January 15, 2000',
      year: 2000,
      month: 1,
      day: 15,
      precision: 11,
    }
    expect(compareDates(a, b)).toBeLessThan(0)
  })

  it('treats null values as 0 for comparison', () => {
    const a: ParsedWikidataDate = {
      display: '2000',
      year: 2000,
      month: null,
      day: null,
      precision: 9,
    }
    const b: ParsedWikidataDate = {
      display: 'January 2000',
      year: 2000,
      month: 1,
      day: null,
      precision: 10,
    }
    // null month (0) < 1
    expect(compareDates(a, b)).toBeLessThan(0)
  })
})

describe('parsePositionQualifiers', () => {
  const createSnak = (time: string, precision: number) => ({
    datavalue: {
      value: {
        time,
        precision,
      },
    },
  })

  describe('single date handling', () => {
    it('parses single start date (P580)', () => {
      const qualifiers = {
        P580: [createSnak('+2017-06-21T00:00:00Z', 11)],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate).not.toBeNull()
      expect(result.startDate?.display).toBe('June 21, 2017')
      expect(result.endDate).toBeNull()
    })

    it('parses single end date (P582)', () => {
      const qualifiers = {
        P582: [createSnak('+2023-01-18T00:00:00Z', 11)],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate).toBeNull()
      expect(result.endDate).not.toBeNull()
      expect(result.endDate?.display).toBe('January 18, 2023')
    })

    it('parses both start and end dates', () => {
      const qualifiers = {
        P580: [createSnak('+2019-10-23T00:00:00Z', 11)],
        P582: [createSnak('+2023-01-18T00:00:00Z', 11)],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate?.display).toBe('October 23, 2019')
      expect(result.endDate?.display).toBe('January 18, 2023')
    })
  })

  describe('multiple date handling', () => {
    it('selects most precise date when multiple P580 values exist', () => {
      const qualifiers = {
        P580: [
          createSnak('+1976-00-00T00:00:00Z', 9), // year only
          createSnak('+1976-11-00T00:00:00Z', 10), // month precision
          createSnak('+1976-11-02T00:00:00Z', 11), // day precision
        ],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate?.display).toBe('November 2, 1976')
      expect(result.startDate?.precision).toBe(11)
    })

    it('selects most precise date when multiple P582 values exist', () => {
      const qualifiers = {
        P582: [
          createSnak('+2008-00-00T00:00:00Z', 9), // year only
          createSnak('+2008-12-31T00:00:00Z', 11), // day precision
        ],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.endDate?.display).toBe('December 31, 2008')
      expect(result.endDate?.precision).toBe(11)
    })

    it('selects earliest date for P580 when precision is equal', () => {
      const qualifiers = {
        P580: [
          createSnak('+1992-00-00T00:00:00Z', 9),
          createSnak('+1976-00-00T00:00:00Z', 9),
          createSnak('+1984-00-00T00:00:00Z', 9),
        ],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate?.year).toBe(1976)
    })

    it('selects latest date for P582 when precision is equal', () => {
      const qualifiers = {
        P582: [
          createSnak('+1992-00-00T00:00:00Z', 9),
          createSnak('+2008-00-00T00:00:00Z', 9),
          createSnak('+2000-00-00T00:00:00Z', 9),
        ],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.endDate?.year).toBe(2008)
    })

    it('handles politician with 9 different terms (Q547153 case)', () => {
      // This tests the case mentioned in the issue where a politician held
      // "delegate" position in 9 different terms
      const qualifiers = {
        P580: [
          createSnak('+1976-00-00T00:00:00Z', 9),
          createSnak('+1980-00-00T00:00:00Z', 9),
          createSnak('+1984-00-00T00:00:00Z', 9),
          createSnak('+1988-00-00T00:00:00Z', 9),
          createSnak('+1992-00-00T00:00:00Z', 9),
          createSnak('+1996-00-00T00:00:00Z', 9),
          createSnak('+2000-00-00T00:00:00Z', 9),
          createSnak('+2004-00-00T00:00:00Z', 9),
          createSnak('+2008-00-00T00:00:00Z', 9),
        ],
      }
      const result = parsePositionQualifiers(qualifiers)
      // Should select earliest (1976)
      expect(result.startDate?.year).toBe(1976)
    })
  })

  describe('edge cases', () => {
    it('returns null dates for empty qualifiers', () => {
      const result = parsePositionQualifiers({})
      expect(result.startDate).toBeNull()
      expect(result.endDate).toBeNull()
    })

    it('returns null for empty P580 array', () => {
      const qualifiers = { P580: [] }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate).toBeNull()
    })

    it('handles missing datavalue in snak', () => {
      const qualifiers = {
        P580: [{}],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate).toBeNull()
    })

    it('handles mixed valid and invalid snaks', () => {
      const qualifiers = {
        P580: [
          {}, // invalid
          createSnak('+2000-00-00T00:00:00Z', 9), // valid
          { datavalue: {} }, // invalid
        ],
      }
      const result = parsePositionQualifiers(qualifiers)
      expect(result.startDate?.year).toBe(2000)
    })
  })
})
