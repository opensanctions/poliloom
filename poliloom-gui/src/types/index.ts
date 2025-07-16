export interface Property {
  id: string;
  type: string;
  value: string;
  source_urls: string[];
}

export interface Position {
  id: string;
  position_name: string;
  start_date: string | null;
  end_date: string | null;
  source_urls: string[];
}

export interface Birthplace {
  id: string;
  location_name: string;
  location_wikidata_id: string | null;
  source_urls: string[];
}

export interface Politician {
  id: string;
  name: string;
  wikidata_id: string | null;
  unconfirmed_properties: Property[];
  unconfirmed_positions: Position[];
  unconfirmed_birthplaces: Birthplace[];
}

export interface EvaluationItem {
  entity_type: string;
  entity_id: string;
  result: "confirmed" | "discarded";
}

export interface EvaluationRequest {
  evaluations: EvaluationItem[];
}

export interface EvaluationResponse {
  success: boolean;
  message: string;
  processed_count: number;
  errors: string[];
}