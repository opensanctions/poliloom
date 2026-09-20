import type { SourceResponse } from './index'

/** Language-keyed entity terms as returned by the backend. */
export interface TermMaps {
  labels: Record<string, string>
  descriptions: Record<string, string>
  aliases: Record<string, string[]>
}

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

/** Canonical Wikibase REST statement document. */
export interface RestStatement {
  id: string
  rank: 'preferred' | 'normal' | 'deprecated'
  property: RestProperty
  value: RestValue
  qualifiers: RestSnak[]
  references: { hash?: string; parts: RestSnak[] }[]
}

export interface JsonPatchOperation {
  op: 'test' | 'replace' | 'add'
  path: string
  value?: unknown
}

export type ActionKind = 'CREATE_STATEMENT' | 'EDIT_STATEMENT'

export interface ActionEvidence {
  id: string
  source: SourceResponse
  supporting_quotes: string[] | null
}

export interface CreateStatementPayload {
  statement: Omit<RestStatement, 'id'>
}

export interface EditStatementPayload {
  patch: JsonPatchOperation[]
}

export interface Action {
  id: string
  kind: ActionKind
  statement_id: string | null
  payload: CreateStatementPayload | EditStatementPayload
  entity_terms: TermMaps | null
  evidence: ActionEvidence[]
  is_accepted: boolean | null
  applied_at: string | null
  error: string | null
}

export interface Statement {
  id: string
  document: RestStatement
  entity_terms: TermMaps | null
}
