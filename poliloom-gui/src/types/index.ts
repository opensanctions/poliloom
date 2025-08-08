export interface ArchivedPageResponse {
  id: string;
  url: string;
  content_hash: string;
  fetch_timestamp: string;
}

export interface Property {
  id: string;
  type: string;
  value: string;
  proof_line: string | null;
  archived_page: ArchivedPageResponse | null;
}

export interface Position {
  id: string;
  position_name: string;
  start_date: string | null;
  end_date: string | null;
  proof_line: string | null;
  archived_page: ArchivedPageResponse | null;
}

export interface Birthplace {
  id: string;
  location_name: string;
  location_wikidata_id: string | null;
  proof_line: string | null;
  archived_page: ArchivedPageResponse | null;
}

export interface Politician {
  id: string;
  name: string;
  wikidata_id: string | null;
  extracted_properties: Property[];
  extracted_positions: Position[];
  extracted_birthplaces: Birthplace[];
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