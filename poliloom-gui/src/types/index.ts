export interface ArchivedPageResponse {
  id: string;
  url: string;
  content_hash: string;
  fetch_timestamp: string;
}

// Base interface for all data items (both existing and extracted)
export interface BaseItem {
  id: string;
}

// Base interface for evaluation items (extracted data with proof)
export interface BaseEvaluationItem extends BaseItem {
  proof_line: string | null;
  archived_page: ArchivedPageResponse | null;
}

// Extracted data interfaces (extend BaseEvaluationItem)
export interface Property extends BaseEvaluationItem {
  type: string;
  value: string;
}

export interface Position extends BaseEvaluationItem {
  position_name: string;
  wikidata_id: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface Birthplace extends BaseEvaluationItem {
  location_name: string;
  wikidata_id: string | null;
}

// Existing Wikidata data interfaces (extend BaseItem only)
export interface WikidataProperty extends BaseItem {
  type: string;
  value: string;
}

export interface WikidataPosition extends BaseItem {
  position_name: string;
  wikidata_id: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface WikidataBirthplace extends BaseItem {
  location_name: string;
  wikidata_id: string | null;
}

export interface Politician {
  id: string;
  name: string;
  wikidata_id: string | null;
  extracted_properties: Property[];
  extracted_positions: Position[];
  extracted_birthplaces: Birthplace[];
  wikidata_properties: WikidataProperty[];
  wikidata_positions: WikidataPosition[];
  wikidata_birthplaces: WikidataBirthplace[];
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