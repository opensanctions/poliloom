import {
  Politician,
  PropertyType,
  ArchivedPageResponse
} from '@/types';

const mockArchivedPage: ArchivedPageResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  content_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
};

export const mockPolitician: Politician = {
  id: 'pol-1',
  name: 'Test Politician',
  wikidata_id: 'Q987654',
  properties: [
    {
      id: 'prop-1',
      type: PropertyType.P569,
      value: '+1970-01-01T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      proof_line: 'born on January 1, 1970',
      archived_page: mockArchivedPage,
    },
    {
      id: 'pos-1',
      type: PropertyType.P39,
      entity_id: 'Q555777',
      entity_name: 'Mayor of Test City',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }]
      },
      proof_line: 'served as mayor from 2020 to 2024',
      archived_page: mockArchivedPage,
    },
    {
      id: 'birth-1',
      type: PropertyType.P19,
      entity_id: 'Q123456',
      entity_name: 'Test City',
      statement_id: null,
      proof_line: 'was born in Test City',
      archived_page: mockArchivedPage,
    }
  ]
};

export const mockEmptyPolitician: Politician = {
  id: 'pol-2',
  name: 'Empty Politician',
  wikidata_id: null,
  properties: []
};

export const mockPoliticianWithConflicts: Politician = {
  id: 'pol-conflicted',
  name: 'Conflicted Politician',
  wikidata_id: 'Q111222',
  properties: [
    // Birth date (conflicted - has extracted data)
    {
      id: 'prop-conflicted',
      type: PropertyType.P569,
      value: '+1970-01-02T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      proof_line: 'born on January 2, 1970',
      archived_page: mockArchivedPage,
    },
    // Citizenship (extracted-only)
    {
      id: 'prop-extracted',
      type: PropertyType.P27,
      entity_id: 'Q142',
      entity_name: 'France',
      statement_id: null,
      proof_line: 'French politician',
      archived_page: mockArchivedPage,
    },
    // Position (conflicted)
    {
      id: 'pos-conflicted',
      type: PropertyType.P39,
      entity_id: 'Q555777',
      entity_name: 'Mayor of Test City',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }]
      },
      proof_line: 'served as mayor from 2020 to 2024',
      archived_page: mockArchivedPage,
    },
    // Position (extracted-only)
    {
      id: 'pos-extracted',
      type: PropertyType.P39,
      entity_id: 'Q777888',
      entity_name: 'Council Member',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2018-01-01T00:00:00Z', precision: 11 } } }]
      },
      proof_line: 'council member since 2018',
      archived_page: mockArchivedPage,
    },
    // Birthplace (conflicted)
    {
      id: 'birth-conflicted',
      type: PropertyType.P19,
      entity_id: 'Q123456',
      entity_name: 'Test City',
      statement_id: null,
      proof_line: 'was born in Test City',
      archived_page: mockArchivedPage,
    },
    // Birthplace (extracted-only)
    {
      id: 'birth-extracted',
      type: PropertyType.P19,
      entity_id: 'Q999000',
      entity_name: 'New City',
      statement_id: null,
      proof_line: 'was born in New City',
      archived_page: mockArchivedPage,
    }
  ]
};

export const mockPoliticianExtractedOnly: Politician = {
  id: 'pol-extracted',
  name: 'Extracted Only Politician',
  wikidata_id: 'Q333444',
  properties: [
    {
      id: 'prop-extracted-only-1',
      type: PropertyType.P569,
      value: '+1980-05-15T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      proof_line: 'born on May 15, 1980',
      archived_page: mockArchivedPage,
    },
    {
      id: 'prop-extracted-only-2',
      type: PropertyType.P27,
      entity_id: 'Q183',
      entity_name: 'Germany',
      statement_id: null,
      proof_line: 'German citizen',
      archived_page: mockArchivedPage,
    },
    {
      id: 'pos-extracted-only-1',
      type: PropertyType.P39,
      entity_id: 'Q111222',
      entity_name: 'Minister of Education',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2019-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2023-01-01T00:00:00Z', precision: 11 } } }]
      },
      proof_line: 'served as minister from 2019 to 2023',
      archived_page: mockArchivedPage,
    },
    {
      id: 'birth-extracted-only-1',
      type: PropertyType.P19,
      entity_id: 'Q64',
      entity_name: 'Berlin',
      statement_id: null,
      proof_line: 'was born in Berlin',
      archived_page: mockArchivedPage,
    }
  ]
};

export const mockPoliticianExistingOnly: Politician = {
  id: 'pol-existing',
  name: 'Existing Only Politician',
  wikidata_id: 'Q555666',
  properties: [] // No unconfirmed properties - everything exists in Wikidata already
};

export const mockPoliticianWithEdgeCases: Politician = {
  id: 'pol-edge-cases',
  name: 'Edge Case Politician',
  wikidata_id: 'Q777888',
  properties: [
    // Wikidata statement (should show as read-only)
    {
      id: 'prop-wikidata-1',
      type: PropertyType.P569,
      value: '+1980-01-01T00:00:00Z',
      value_precision: 11,
      statement_id: 'Q777888$12345678-1234-1234-1234-123456789012',
      proof_line: 'born on January 1, 1980',
      archived_page: mockArchivedPage, // Should be hidden because statement_id exists
    },
    // Regular extracted statement
    {
      id: 'prop-extracted-1',
      type: PropertyType.P569,
      value: '+1980-01-02T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      proof_line: 'born on January 2, 1980',
      archived_page: mockArchivedPage,
    },
    // Wikidata position statement
    {
      id: 'pos-wikidata-1',
      type: PropertyType.P39,
      entity_id: 'Q123456',
      entity_name: 'Mayor',
      statement_id: 'Q123456$87654321-4321-4321-4321-210987654321',
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }]
      },
      proof_line: 'served as mayor from 2020 to 2024',
      archived_page: mockArchivedPage, // Should be hidden
    },
    // Wikidata birthplace statement
    {
      id: 'birth-wikidata-1',
      type: PropertyType.P19,
      entity_id: 'Q987654',
      entity_name: 'Test City',
      statement_id: 'Q987654$11111111-2222-3333-4444-555555555555',
      proof_line: 'was born in Test City',
      archived_page: mockArchivedPage, // Should be hidden
    }
  ]
};