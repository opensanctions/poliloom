import { Politician, Property, Position, Birthplace, ArchivedPageResponse } from '@/types';

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
  start_date: '2020-01-01',
  end_date: '2024-01-01',
  proof_line: 'served as mayor from 2020 to 2024',
  archived_page: mockArchivedPage,
};

export const mockBirthplace: Birthplace = {
  id: 'birth-1',
  location_name: 'Test City',
  location_wikidata_id: 'Q123456',
  proof_line: 'was born in Test City',
  archived_page: mockArchivedPage,
};

export const mockPolitician: Politician = {
  id: 'pol-1',
  name: 'Test Politician',
  wikidata_id: 'Q987654',
  unconfirmed_properties: [mockProperty],
  unconfirmed_positions: [mockPosition],
  unconfirmed_birthplaces: [mockBirthplace],
};

export const mockEmptyPolitician: Politician = {
  id: 'pol-2',
  name: 'Empty Politician',
  wikidata_id: null,
  unconfirmed_properties: [],
  unconfirmed_positions: [],
  unconfirmed_birthplaces: [],
};

export const createMockPolitician = (overrides?: Partial<Politician>): Politician => ({
  ...mockPolitician,
  ...overrides,
});