import type { CountryResponse, LanguageResponse, SearchEntity, TermLabels, TermMaps } from '@/types'

// Typed factories for backend-mirrored response types. Each returns a
// complete, schema-exact object; tests override only the fields they
// exercise, so a fixture that diverges from the mirrored contract fails
// to compile.

export const terms = (labels: Record<string, string>): TermMaps => ({
  labels,
  descriptions: {},
  aliases: {},
})

/** Term map of the list endpoints, which ship labels only. */
export const labelTerms = (labels: Record<string, string>): TermLabels => ({ labels })

export function language(overrides: Partial<LanguageResponse> = {}): LanguageResponse {
  return {
    wikidata_id: 'Q1860',
    terms: labelTerms({ en: 'English' }),
    wikimedia_code: 'en',
    iso_639_1: 'en',
    iso_639_3: 'eng',
    sources_count: 0,
    ...overrides,
  }
}

export function country(overrides: Partial<CountryResponse> = {}): CountryResponse {
  return {
    wikidata_id: 'Q30',
    terms: labelTerms({ en: 'United States' }),
    citizenships_count: 0,
    ...overrides,
  }
}

export function searchEntity(overrides: Partial<SearchEntity> = {}): SearchEntity {
  return {
    wikidata_id: 'Q64',
    terms: {
      labels: { en: 'Berlin' },
      descriptions: { en: 'capital of Germany' },
      aliases: {},
    },
    ...overrides,
  }
}
