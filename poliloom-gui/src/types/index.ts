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

export interface ConfirmationRequest {
  confirmed_properties: string[];
  discarded_properties: string[];
  confirmed_positions: string[];
  discarded_positions: string[];
  confirmed_birthplaces: string[];
  discarded_birthplaces: string[];
}