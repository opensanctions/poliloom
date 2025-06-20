export interface Property {
  id: string;
  type: "BirthDate" | "BirthPlace";
  value: string;
  source_url: string;
}

export interface Position {
  id: string;
  position_name: string;
  start_date: string;
  end_date: string;
  source_url: string;
}

export interface Politician {
  id: string;
  name: string;
  country: string;
  unconfirmed_properties: Property[];
  unconfirmed_positions: Position[];
}

export interface ConfirmationRequest {
  confirmed_properties: string[];
  discarded_properties: string[];
  confirmed_positions: string[];
  discarded_positions: string[];
}