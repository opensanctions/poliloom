import type { SourceResponse } from './index'

/** Language-keyed entity terms as returned by the backend. */
export interface TermMaps {
  labels: Record<string, string>
  descriptions: Record<string, string>
  aliases: Record<string, string[]>
}

/** Labels-only term map, as sent by the list endpoints. */
export type TermLabels = Pick<TermMaps, 'labels'>

export interface RestProperty {
  id: string
  data_type?: string
}

// Entity-valued content is a QID string; time-valued content is a RestTimeValue.
export interface RestValue {
  type: 'value' | 'somevalue' | 'novalue'
  content?: unknown
}

export interface RestTimeValue {
  time: string
  precision: number
  calendarmodel: string
}

export interface RestSnak {
  property: RestProperty
  value: RestValue
}

/** A reference attached to a statement. */
export interface RestReference {
  hash?: string
  parts: RestSnak[]
}

/** The data-bearing part of a statement, without server metadata. */
export interface StatementFact {
  property: RestProperty
  value: RestValue
  qualifiers: RestSnak[]
}

/** Canonical Wikibase REST statement document. */
export interface RestStatement extends StatementFact {
  id: string
  rank: 'preferred' | 'normal' | 'deprecated'
  references: RestReference[]
}

export type ActionChange = 'add' | 'refine' | 'reference'

export interface ActionEvidence {
  id: string
  source: SourceResponse
  supporting_quotes: string[] | null
}

export interface Action {
  id: string
  target_wikidata_statement_id: string | null
  before: StatementFact | null
  after: StatementFact
  references_to_add: RestReference[]
  group_key: string
  change: ActionChange
  entity_terms: TermMaps | null
  evidence: ActionEvidence[]
}

export interface Statement {
  id: string
  document: RestStatement
  entity_terms: TermMaps | null
}
