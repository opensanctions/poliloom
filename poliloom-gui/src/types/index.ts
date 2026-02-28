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

export interface PropertyReference {
  id: string
  archived_page: ArchivedPageResponse
  supporting_quotes?: string[]
}

export interface Property {
  id: string
  type: PropertyType
  value?: string
  value_precision?: number
  entity_id?: string
  entity_name?: string
  statement_id?: string | null
  qualifiers?: PropertyQualifiers
  references?: Array<Record<string, unknown>>
  sources: PropertyReference[]
  userAdded?: boolean // true for properties manually added by user on the client
  evaluation?: boolean // undefined = not evaluated, true = accepted, false = rejected (derived from action list)
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

export interface NextPoliticianResponse {
  wikidata_id: string | null
  meta: EnrichmentMetadata
}

export interface AcceptPropertyItem {
  action: 'accept'
  id: string
}

export interface RejectPropertyItem {
  action: 'reject'
  id: string
}

export interface CreatePropertyItem {
  action: 'create'
  id: string // Temporary client-side ID (ignored by backend)
  type: string
  value?: string
  value_precision?: number
  entity_id?: string
  entity_name?: string
  qualifiers?: PropertyQualifiers
}

export type PropertyActionItem = AcceptPropertyItem | RejectPropertyItem | CreatePropertyItem

export interface PatchPropertiesRequest {
  items: PropertyActionItem[]
}

export interface SourcePatchPropertiesRequest {
  items: Record<string, PropertyActionItem[]>
}

export interface SourceResponse {
  archived_page: ArchivedPageResponse
  politicians: Politician[]
}

export interface PatchPropertiesResponse {
  success: boolean
  message: string
  errors: string[]
}

export interface CreatePoliticianRequest {
  name: string
  items: CreatePropertyItem[]
}

export interface CreatePoliticianResponse {
  success: boolean
  wikidata_id?: string
  message: string
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
  iso_639_1?: string
  iso_639_3?: string
  sources_count: number
}

export interface CountryResponse extends WikidataEntity {
  citizenships_count: number
}

export interface EvaluationTimeseriesPoint {
  date: string
  accepted: number
  rejected: number
}

export interface CountryCoverage {
  wikidata_id: string | null // null for stateless politicians
  name: string
  evaluated_count: number // enriched + evaluated
  enriched_count: number // enriched within cooldown
  total_count: number // all politicians
}

export interface StatsResponse {
  evaluations_timeseries: EvaluationTimeseriesPoint[]
  country_coverage: CountryCoverage[] // includes stateless as wikidata_id=null
  cooldown_days: number
}
