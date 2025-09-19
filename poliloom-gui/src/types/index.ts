export interface ArchivedPageResponse {
  id: string;
  url: string;
  content_hash: string;
  fetch_timestamp: string;
}

// Base interface for all statement items
export interface BaseEvaluationItem {
  id: string;
  statement_id: string | null;
  proof_line: string | null;
  archived_page: ArchivedPageResponse | null;
}

// Property statement
export interface PropertyStatement extends BaseEvaluationItem {
  value: string;
  value_precision: number | null;
}

// Position statement
export interface PositionStatement extends BaseEvaluationItem {
  start_date: string | null;
  start_date_precision: number | null;
  end_date: string | null;
  end_date_precision: number | null;
}

// Birthplace statement
export type BirthplaceStatement = BaseEvaluationItem

// Grouped data interfaces
export interface PropertyGroup {
  type: string;
  statements: PropertyStatement[];
}

export interface PositionGroup {
  qid: string;
  name: string;
  statements: PositionStatement[];
}

export interface BirthplaceGroup {
  qid: string;
  name: string;
  statements: BirthplaceStatement[];
}

export interface Politician {
  id: string;
  name: string;
  wikidata_id: string | null;
  properties: PropertyGroup[];
  positions: PositionGroup[];
  birthplaces: BirthplaceGroup[];
}

export interface PropertyEvaluationItem {
  id: string;
  is_confirmed: boolean;
}

export interface PositionEvaluationItem {
  id: string;
  is_confirmed: boolean;
}

export interface BirthplaceEvaluationItem {
  id: string;
  is_confirmed: boolean;
}

export interface EvaluationRequest {
  property_evaluations: PropertyEvaluationItem[];
  position_evaluations: PositionEvaluationItem[];
  birthplace_evaluations: BirthplaceEvaluationItem[];
}

export interface EvaluationResponse {
  success: boolean;
  message: string;
  property_count: number;
  position_count: number;
  birthplace_count: number;
  errors: string[];
}