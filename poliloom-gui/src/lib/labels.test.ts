import { describe, expect, it } from 'vitest'
import { best_label } from '@/lib/labels'
import type { TermMaps } from '@/types'

function terms(labels: Record<string, string>): TermMaps {
  return { labels, descriptions: {}, aliases: {} }
}

describe('best_label', () => {
  it('returns the label of the first user language that has one', () => {
    const maps = terms({ en: 'English', de: 'Deutsch' })

    expect(best_label(maps, ['de', 'en'], 'Q42')).toBe('Deutsch')
  })

  it('prefers a user language over mul and en', () => {
    const maps = terms({ mul: 'Multiple languages', en: 'English', de: 'Deutsch' })

    expect(best_label(maps, ['de'], 'Q42')).toBe('Deutsch')
  })

  it('skips user languages without a label', () => {
    const maps = terms({ fr: 'Français', en: 'English' })

    expect(best_label(maps, ['de', 'fr'], 'Q42')).toBe('Français')
  })

  it('falls back to mul when no user language matches', () => {
    const maps = terms({ mul: 'Multiple languages', es: 'España' })

    expect(best_label(maps, ['de', 'fr'], 'Q42')).toBe('Multiple languages')
  })

  it('falls back to en when no user language or mul matches', () => {
    const maps = terms({ en: 'English', es: 'España' })

    expect(best_label(maps, ['de', 'fr'], 'Q42')).toBe('English')
  })

  it('falls back to the first label in the map', () => {
    const maps = terms({ es: 'España', fr: 'France' })

    expect(best_label(maps, ['de'], 'Q42')).toBe('España')
  })

  it('skips empty labels', () => {
    const maps = terms({ de: '', en: 'English' })

    expect(best_label(maps, ['de', 'en'], 'Q42')).toBe('English')
  })

  it('returns the fallback when there are no labels', () => {
    expect(best_label(terms({}), ['de'], 'Q42')).toBe('Q42')
  })

  it('returns the fallback when terms is null or undefined', () => {
    expect(best_label(null, ['de'], 'Q42')).toBe('Q42')
    expect(best_label(undefined, ['de'], 'Q42')).toBe('Q42')
  })
})
