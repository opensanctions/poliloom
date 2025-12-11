export interface ArchivedPageResponse {
  id: string
  url: string
  content_hash: string
  fetch_timestamp: string
}

export enum PropertyType {
  P569 = 'P569', // Birth Date
  P570 = 'P570', // Death Date
  P19 = 'P19', // Birthplace
  P39 = 'P39', // Position
  P27 = 'P27', // Citizenship
}

// Qualifier types for Wikidata date values
export interface WikidataDateValue {
  time: string
  precision: number
}

export interface WikidataQualifierValue {
  datavalue?: {
    value?: WikidataDateValue
  }
}

export interface PropertyQualifiers {
  P580?: WikidataQualifierValue[] // Start date
  P582?: WikidataQualifierValue[] // End date
  [key: string]: WikidataQualifierValue[] | undefined
}

export interface Property {
  key: string // Used for React keys and Map lookups
  id?: string // Optional: Present for backend properties, absent for manually added properties
  type: PropertyType
  value?: string
  value_precision?: number
  entity_id?: string
  entity_name?: string
  supporting_quotes?: string[]
  statement_id?: string | null
  qualifiers?: PropertyQualifiers
  references?: Array<Record<string, unknown>>
  archived_page?: ArchivedPageResponse
}

export interface Politician {
  id: string
  name: string
  wikidata_id: string | null
  properties: Property[]
}

export interface EnrichmentMetadata {
  has_enrichable_politicians: boolean
  total_matching_filters: number
}

export interface PoliticiansListResponse {
  politicians: Politician[]
  meta: EnrichmentMetadata
}

export interface EvaluationItem {
  id: string
  is_accepted: boolean
}

export interface EvaluationRequest {
  evaluations: EvaluationItem[]
}

export interface EvaluationResponse {
  success: boolean
  message: string
  evaluation_count: number
  errors: string[]
}

export interface WikidataEntity {
  wikidata_id: string
  name: string
}

export interface PreferenceResponse extends WikidataEntity {
  preference_type: string
}

export enum PreferenceType {
  LANGUAGE = 'language',
  COUNTRY = 'country',
}

export interface LanguageResponse extends WikidataEntity {
  iso1_code?: string
  iso3_code?: string
  sources_count: number
}

export interface CountryResponse extends WikidataEntity {
  iso_code?: string
  citizenships_count: number
}

export interface EvaluationTimeseriesPoint {
  date: string
  accepted: number
  rejected: number
}

export interface CountryCoverage {
  wikidata_id: string
  name: string
  enriched_count: number
  total_count: number
}

export interface StatsResponse {
  evaluations_timeseries: EvaluationTimeseriesPoint[]
  country_coverage: CountryCoverage[]
  stateless_enriched_count: number
  stateless_total_count: number
  cooldown_days: number
}
