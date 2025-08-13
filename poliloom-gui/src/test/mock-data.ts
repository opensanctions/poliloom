import { Politician, Property, Position, Birthplace, WikidataProperty, WikidataPosition, WikidataBirthplace, ArchivedPageResponse } from '@/types';

export const mockArchivedPage: ArchivedPageResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  content_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
};

export const mockProperty: Property = {
  id: 'prop-1',
  type: 'birth_date',
  value: '1970-01-01',
  proof_line: 'born on January 1, 1970',
  archived_page: mockArchivedPage,
};

export const mockPosition: Position = {
  id: 'pos-1',
  position_name: 'Mayor of Test City',
  wikidata_id: 'Q555777',
  start_date: '2020-01-01',
  end_date: '2024-01-01',
  proof_line: 'served as mayor from 2020 to 2024',
  archived_page: mockArchivedPage,
};

export const mockBirthplace: Birthplace = {
  id: 'birth-1',
  location_name: 'Test City',
  wikidata_id: 'Q123456',
  proof_line: 'was born in Test City',
  archived_page: mockArchivedPage,
};

export const mockWikidataProperty: WikidataProperty = {
  id: 'wd-prop-1',
  type: 'birth_date',
  value: '1969-12-31',
};

export const mockWikidataPosition: WikidataPosition = {
  id: 'wd-pos-1',
  position_name: 'City Council Member',
  wikidata_id: 'Q444666',
  start_date: '2018-01-01',
  end_date: '2019-12-31',
};

export const mockWikidataBirthplace: WikidataBirthplace = {
  id: 'wd-birth-1',
  location_name: 'Old Town',
  wikidata_id: 'Q111222',
};

export const mockPolitician: Politician = {
  id: 'pol-1',
  name: 'Test Politician',
  wikidata_id: 'Q987654',
  extracted_properties: [mockProperty],
  extracted_positions: [mockPosition],
  extracted_birthplaces: [mockBirthplace],
  wikidata_properties: [mockWikidataProperty],
  wikidata_positions: [mockWikidataPosition],
  wikidata_birthplaces: [mockWikidataBirthplace],
};

export const mockEmptyPolitician: Politician = {
  id: 'pol-2',
  name: 'Empty Politician',
  wikidata_id: null,
  extracted_properties: [],
  extracted_positions: [],
  extracted_birthplaces: [],
  wikidata_properties: [],
  wikidata_positions: [],
  wikidata_birthplaces: [],
};

export const createMockPolitician = (overrides?: Partial<Politician>): Politician => ({
  ...mockPolitician,
  ...overrides,
});

// Additional mock data for testing merged functionality

// Conflicted data - same type/name but different values
export const mockConflictedProperty: Property = {
  id: 'prop-conflict',
  type: 'birth_date',
  value: '1970-01-02',
  proof_line: 'born on January 2, 1970',
  archived_page: mockArchivedPage,
};

export const mockConflictedPosition: Position = {
  id: 'pos-conflict',
  position_name: 'Mayor of Test City',
  wikidata_id: 'Q555777',
  start_date: '2020-01-01',
  end_date: '2024-06-01', // Different end date
  proof_line: 'served as mayor until June 2024',
  archived_page: mockArchivedPage,
};

// Extracted-only data - no matching existing data
export const mockExtractedOnlyProperty: Property = {
  id: 'prop-extracted',
  type: 'nationality',
  value: 'American',
  proof_line: 'nationality is American',
  archived_page: mockArchivedPage,
};

export const mockExtractedOnlyPosition: Position = {
  id: 'pos-extracted',
  position_name: 'Governor',
  wikidata_id: 'Q999888',
  start_date: '2025-01-01',
  end_date: null,
  proof_line: 'elected as governor',
  archived_page: mockArchivedPage,
};

export const mockExtractedOnlyBirthplace: Birthplace = {
  id: 'birth-extracted',
  location_name: 'Another City',
  wikidata_id: 'Q777888',
  proof_line: 'also born in Another City',
  archived_page: mockArchivedPage,
};

// Existing-only data - no matching extracted data
export const mockExistingOnlyProperty: WikidataProperty = {
  id: 'wd-existing',
  type: 'death_date',
  value: '2050-01-01',
};

export const mockExistingOnlyPosition: WikidataPosition = {
  id: 'wd-existing-pos',
  position_name: 'Senator',
  wikidata_id: 'Q111333',
  start_date: '2015-01-01',
  end_date: '2018-12-31',
};

export const mockExistingOnlyBirthplace: WikidataBirthplace = {
  id: 'wd-existing-birth',
  location_name: 'Capital City',
  wikidata_id: 'Q555999',
};

// Politicians with different merge scenarios
export const mockPoliticianWithConflicts: Politician = {
  id: 'pol-conflicts',
  name: 'Conflicted Politician',
  wikidata_id: 'Q111111',
  extracted_properties: [mockConflictedProperty, mockExtractedOnlyProperty],
  extracted_positions: [mockConflictedPosition, mockExtractedOnlyPosition],
  extracted_birthplaces: [mockBirthplace, mockExtractedOnlyBirthplace],
  wikidata_properties: [mockWikidataProperty, mockExistingOnlyProperty],
  wikidata_positions: [mockWikidataPosition, mockExistingOnlyPosition],
  wikidata_birthplaces: [mockWikidataBirthplace, mockExistingOnlyBirthplace],
};

export const mockPoliticianExtractedOnly: Politician = {
  id: 'pol-extracted',
  name: 'Extracted Only Politician',
  wikidata_id: 'Q222222',
  extracted_properties: [mockExtractedOnlyProperty],
  extracted_positions: [mockExtractedOnlyPosition],
  extracted_birthplaces: [mockExtractedOnlyBirthplace],
  wikidata_properties: [],
  wikidata_positions: [],
  wikidata_birthplaces: [],
};

export const mockPoliticianExistingOnly: Politician = {
  id: 'pol-existing',
  name: 'Existing Only Politician',
  wikidata_id: 'Q333333',
  extracted_properties: [],
  extracted_positions: [],
  extracted_birthplaces: [],
  wikidata_properties: [mockExistingOnlyProperty],
  wikidata_positions: [mockExistingOnlyPosition],
  wikidata_birthplaces: [mockExistingOnlyBirthplace],
};