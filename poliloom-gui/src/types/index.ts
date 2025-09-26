export interface ArchivedPageResponse {
  id: string;
  url: string;
  content_hash: string;
  fetch_timestamp: string;
}

export enum PropertyType {
  P569 = "P569", // Birth Date
  P570 = "P570", // Death Date
  P19 = "P19",   // Birthplace
  P39 = "P39",   // Position
  P27 = "P27",   // Citizenship
}

export interface Property {
  id: string;
  type: PropertyType;
  value?: string;
  value_precision?: number;
  entity_id?: string;
  entity_name?: string;
  proof_line?: string;
  statement_id?: string;
  qualifiers?: Record<string, any>;
  references?: Array<Record<string, any>>;
  archived_page?: ArchivedPageResponse;
}

export interface Politician {
  id: string;
  name: string;
  wikidata_id: string | null;
  properties: Property[];
}

export interface EvaluationItem {
  id: string;
  is_confirmed: boolean;
}

export interface EvaluationRequest {
  evaluations: EvaluationItem[];
}

export interface EvaluationResponse {
  success: boolean;
  message: string;
  evaluation_count: number;
  errors: string[];
}