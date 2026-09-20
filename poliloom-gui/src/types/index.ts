import type { Action, Statement, TermMaps } from './wikibase'

export type SourceStatus = 'processing' | 'done'

export interface SourceResponse {
  id: string
  url: string
  url_hash: string | null
  fetch_timestamp: string | null
  status: SourceStatus
  error?: string | null
  http_status_code?: number | null
  language_qids: string[]
}

export interface Politician {
  id: string
  wikidata_id: string | null
  terms: TermMaps
  sources: SourceResponse[]
  statements: Statement[]
  actions: Action[]
}

export interface EnrichmentMetadata {
  has_enrichable_politicians: boolean
}

export interface NextPoliticianResponse {
  wikidata_id: string | null
  meta: EnrichmentMetadata
}

export interface CreatePoliticianRequest {
  name: string
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

export interface SearchEntity extends WikidataEntity {
  description?: string
}

export type SearchFn = (query: string) => Promise<SearchEntity[]>

export interface UserSettings {
  advanced_mode: boolean
  basic_tutorial_completed: boolean
  advanced_tutorial_completed: boolean
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
  wikidata_id: string | null // null for politicians without citizenship
  name: string
  evaluated_count: number // enriched + evaluated
  enriched_count: number // enriched within cooldown
  total_count: number // all politicians
}

export interface StatsResponse {
  evaluations_timeseries: EvaluationTimeseriesPoint[]
  country_coverage: CountryCoverage[] // includes politicians without citizenship as wikidata_id=null
  cooldown_days: number
}

// SSE event types

export interface SourceStatusEvent {
  type: 'source_status'
  politician_ids: string[]
  source_id: string
  status: string
  error?: string
  http_status_code?: number
}

export interface EnrichmentCompleteEvent {
  type: 'enrichment_complete'
  languages: string[]
  countries: string[]
}

export interface EvaluationCountEvent {
  type: 'evaluation_count'
  total: number
}

export type SSEEvent = SourceStatusEvent | EnrichmentCompleteEvent | EvaluationCountEvent

export type SSEEventType = SSEEvent['type']

export type SSEEventByType<T extends SSEEventType> = Extract<SSEEvent, { type: T }>

export * from './wikibase'
