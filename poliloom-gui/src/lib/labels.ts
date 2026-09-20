import type { TermMaps } from '@/types'

export function best_label(
  terms: TermMaps | null | undefined,
  user_languages: string[],
  fallback: string,
): string {
  if (terms) {
    for (const language of [...user_languages, 'mul', 'en']) {
      const label = terms.labels[language]
      if (label) return label
    }
    const anyLabel = Object.values(terms.labels)[0]
    if (anyLabel !== undefined) return anyLabel
  }
  return fallback
}
