import { describe, it, expect } from 'vitest'
import { parseTimeValue, timeValue } from './dateParser'
import type { RestTimeValue } from '@/types'

const time = (time: string, precision: number): RestTimeValue => ({
  time,
  precision,
  calendarmodel: 'http://www.wikidata.org/entity/Q1985727',
})

describe('parseTimeValue', () => {
  it('formats day precision as a long date', () => {
    expect(parseTimeValue(time('+2017-06-21T00:00:00Z', 11)).display).toBe('June 21, 2017')
  })

  it('formats month precision as month and year', () => {
    expect(parseTimeValue(time('+2017-06-00T00:00:00Z', 10)).display).toBe('June 2017')
  })

  it('formats year precision as the year alone', () => {
    expect(parseTimeValue(time('+2017-00-00T00:00:00Z', 9)).display).toBe('2017')
  })

  it('falls back to the year when day precision has unknown month and day', () => {
    const parsed = parseTimeValue(time('+2017-00-00T00:00:00Z', 11))
    expect(parsed.display).toBe('2017')
    expect(parsed.month).toBeNull()
    expect(parsed.day).toBeNull()
  })

  it('exposes parsed components', () => {
    const parsed = parseTimeValue(time('+2017-06-21T00:00:00Z', 11))
    expect(parsed).toEqual({
      display: 'June 21, 2017',
      year: 2017,
      month: 6,
      day: 21,
      precision: 11,
    })
  })
})

describe('timeValue', () => {
  it('extracts time content from a value snak', () => {
    expect(timeValue({ type: 'value', content: time('+2017-06-21T00:00:00Z', 11) })).toEqual(
      time('+2017-06-21T00:00:00Z', 11),
    )
  })

  it('returns null for somevalue and novalue', () => {
    expect(timeValue({ type: 'somevalue' })).toBeNull()
    expect(timeValue({ type: 'novalue' })).toBeNull()
  })

  it('returns null for non-time content', () => {
    expect(timeValue({ type: 'value', content: 'Q42' })).toBeNull()
    expect(timeValue({ type: 'value', content: { time: '+2017-00-00T00:00:00Z' } })).toBeNull()
    expect(timeValue({ type: 'value' })).toBeNull()
  })
})
