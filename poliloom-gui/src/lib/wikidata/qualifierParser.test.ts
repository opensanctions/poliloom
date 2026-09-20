import { describe, it, expect } from 'vitest'
import { compareTimes, findQualifiers, formatTimeframe, parseTimeframe } from './qualifierParser'
import type { ParsedTime } from './dateParser'
import type { RestSnak } from '@/types'

const timeSnak = (propertyId: string, time: string, precision: number): RestSnak => ({
  property: { id: propertyId },
  value: { type: 'value', content: { time, precision, calendarmodel: 'Q1985727' } },
})

const startSnak = (time: string, precision: number) => timeSnak('P580', time, precision)
const endSnak = (time: string, precision: number) => timeSnak('P582', time, precision)

describe('findQualifiers', () => {
  it('finds qualifiers by property id', () => {
    const qualifiers = [
      startSnak('+2019-10-23T00:00:00Z', 11),
      endSnak('+2023-01-18T00:00:00Z', 11),
    ]

    expect(findQualifiers(qualifiers, 'P580')).toEqual([qualifiers[0]])
    expect(findQualifiers(qualifiers, 'P582')).toEqual([qualifiers[1]])
    expect(findQualifiers(qualifiers, 'P1365')).toEqual([])
  })
})

describe('compareTimes', () => {
  const parsed = (year: number, month: number | null, day: number | null): ParsedTime => ({
    display: '',
    year,
    month,
    day,
    precision: 11,
  })

  it('compares by year first', () => {
    expect(compareTimes(parsed(1990, null, null), parsed(2000, null, null))).toBeLessThan(0)
    expect(compareTimes(parsed(2000, null, null), parsed(1990, null, null))).toBeGreaterThan(0)
  })

  it('compares by month when years are equal', () => {
    expect(compareTimes(parsed(2000, 1, null), parsed(2000, 3, null))).toBeLessThan(0)
  })

  it('compares by day when year and month are equal', () => {
    expect(compareTimes(parsed(2000, 1, 1), parsed(2000, 1, 15))).toBeLessThan(0)
  })

  it('returns 0 for equal times', () => {
    expect(compareTimes(parsed(2000, 1, 1), parsed(2000, 1, 1))).toBe(0)
  })

  it('treats null components as 0', () => {
    expect(compareTimes(parsed(2000, null, null), parsed(2000, 1, null))).toBeLessThan(0)
  })
})

describe('parseTimeframe', () => {
  describe('single date handling', () => {
    it('parses a single start date (P580)', () => {
      const result = parseTimeframe([startSnak('+2017-06-21T00:00:00Z', 11)])
      expect(result.start?.display).toBe('June 21, 2017')
      expect(result.end).toBeNull()
    })

    it('parses a single end date (P582)', () => {
      const result = parseTimeframe([endSnak('+2023-01-18T00:00:00Z', 11)])
      expect(result.start).toBeNull()
      expect(result.end?.display).toBe('January 18, 2023')
    })

    it('parses both start and end dates', () => {
      const result = parseTimeframe([
        startSnak('+2019-10-23T00:00:00Z', 11),
        endSnak('+2023-01-18T00:00:00Z', 11),
      ])
      expect(result.start?.display).toBe('October 23, 2019')
      expect(result.end?.display).toBe('January 18, 2023')
    })
  })

  describe('multiple date handling', () => {
    it('selects the most precise date when multiple P580 values exist', () => {
      const result = parseTimeframe([
        startSnak('+1976-00-00T00:00:00Z', 9), // year only
        startSnak('+1976-11-00T00:00:00Z', 10), // month precision
        startSnak('+1976-11-02T00:00:00Z', 11), // day precision
      ])
      expect(result.start?.display).toBe('November 2, 1976')
      expect(result.start?.precision).toBe(11)
    })

    it('selects the most precise date when multiple P582 values exist', () => {
      const result = parseTimeframe([
        endSnak('+2008-00-00T00:00:00Z', 9), // year only
        endSnak('+2008-12-31T00:00:00Z', 11), // day precision
      ])
      expect(result.end?.display).toBe('December 31, 2008')
      expect(result.end?.precision).toBe(11)
    })

    it('selects the earliest date for P580 when precision is equal', () => {
      const result = parseTimeframe([
        startSnak('+1992-00-00T00:00:00Z', 9),
        startSnak('+1976-00-00T00:00:00Z', 9),
        startSnak('+1984-00-00T00:00:00Z', 9),
      ])
      expect(result.start?.year).toBe(1976)
    })

    it('selects the latest date for P582 when precision is equal', () => {
      const result = parseTimeframe([
        endSnak('+1992-00-00T00:00:00Z', 9),
        endSnak('+2008-00-00T00:00:00Z', 9),
        endSnak('+2000-00-00T00:00:00Z', 9),
      ])
      expect(result.end?.year).toBe(2008)
    })

    it('handles a politician with 9 different terms (Q547153 case)', () => {
      const result = parseTimeframe([
        startSnak('+1976-00-00T00:00:00Z', 9),
        startSnak('+1980-00-00T00:00:00Z', 9),
        startSnak('+1984-00-00T00:00:00Z', 9),
        startSnak('+1988-00-00T00:00:00Z', 9),
        startSnak('+1992-00-00T00:00:00Z', 9),
        startSnak('+1996-00-00T00:00:00Z', 9),
        startSnak('+2000-00-00T00:00:00Z', 9),
        startSnak('+2004-00-00T00:00:00Z', 9),
        startSnak('+2008-00-00T00:00:00Z', 9),
      ])
      // Should select the earliest (1976)
      expect(result.start?.year).toBe(1976)
    })
  })

  describe('edge cases', () => {
    it('returns null dates for no qualifiers', () => {
      const result = parseTimeframe([])
      expect(result.start).toBeNull()
      expect(result.end).toBeNull()
    })

    it('ignores non-time qualifiers', () => {
      const result = parseTimeframe([
        { property: { id: 'P580' }, value: { type: 'somevalue' } },
        { property: { id: 'P580' }, value: { type: 'value', content: 'Q42' } },
        { property: { id: 'P1365' }, value: { type: 'value', content: 'Q42' } },
      ])
      expect(result.start).toBeNull()
      expect(result.end).toBeNull()
    })
  })
})

describe('formatTimeframe', () => {
  const start = parseTimeframe([startSnak('+2019-10-23T00:00:00Z', 11)]).start!
  const end = parseTimeframe([endSnak('+2023-01-18T00:00:00Z', 11)]).end!

  it('renders a bounded timeframe', () => {
    expect(formatTimeframe({ start, end })).toBe('October 23, 2019 – January 18, 2023')
  })

  it('renders an open-ended timeframe as present', () => {
    expect(formatTimeframe({ start, end: null })).toBe('October 23, 2019 – present')
  })

  it('renders an end-only timeframe as until', () => {
    expect(formatTimeframe({ start: null, end })).toBe('until January 18, 2023')
  })

  it('renders an unspecified timeframe', () => {
    expect(formatTimeframe({ start: null, end: null })).toBe('dates not specified')
  })
})
