import type { TermLabels, TermMaps } from '@/types'

/** First term in the preferred languages, then `mul`, `en`, then any available. */
function best_term(terms: Record<string, string>, languages: string[]): string | undefined {
  for (const language of [...languages, 'mul', 'en']) {
    const term = terms[language]
    if (term) return term
  }
  return Object.values(terms)[0]
}

export function best_label(
  terms: TermLabels | null | undefined,
  languages: string[],
  fallback: string,
): string {
  return (terms && best_term(terms.labels, languages)) ?? fallback
}

export function best_description(
  terms: TermMaps | null | undefined,
  languages: string[],
): string | undefined {
  return terms ? best_term(terms.descriptions, languages) : undefined
}
