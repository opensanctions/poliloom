import {
  Politician,
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
  properties: [{
    type: 'birth_date',
    statements: [{
      id: 'prop-1',
      statement_id: null,
      value: '1970-01-01',
      value_precision: 9,
      proof_line: 'born on January 1, 1970',
      archived_page: mockArchivedPage,
    }],
  }],
  positions: [{
    qid: 'Q555777',
    name: 'Mayor of Test City',
    statements: [{
      id: 'pos-1',
      statement_id: null,
      start_date: '2020-01-01',
      start_date_precision: 9,
      end_date: '2024-01-01',
      end_date_precision: 9,
      proof_line: 'served as mayor from 2020 to 2024',
      archived_page: mockArchivedPage,
    }],
  }],
  birthplaces: [{
    qid: 'Q123456',
    name: 'Test City',
    statements: [{
      id: 'birth-1',
      statement_id: null,
      proof_line: 'was born in Test City',
      archived_page: mockArchivedPage,
    }],
  }],
};

export const mockEmptyPolitician: Politician = {
  id: 'pol-2',
  name: 'Empty Politician',
  wikidata_id: null,
  properties: [],
  positions: [],
  birthplaces: [],
};

// Mock politicians with different data scenarios for comprehensive testing
export const mockPoliticianWithConflicts: Politician = {
  id: 'pol-conflicted',
  name: 'Conflicted Politician',
  wikidata_id: 'Q111222',
  properties: [
    // existing-only property (death_date)
    {
      type: 'death_date',
      statements: []
    },
    // conflicted property (birth_date) - has both existing and extracted
    {
      type: 'birth_date',
      statements: [
        {
          id: 'prop-conflicted',
          statement_id: null,
          value: '1970-01-02',
          value_precision: 9,
          proof_line: 'born on January 2, 1970',
          archived_page: mockArchivedPage,
        }
      ]
    },
    // extracted-only property (nationality)
    {
      type: 'nationality',
      statements: [
        {
          id: 'prop-extracted',
          statement_id: null,
          value: 'French',
          value_precision: null,
          proof_line: 'French politician',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
  positions: [
    // existing-only position
    {
      qid: 'Q888999',
      name: 'Former Mayor',
      statements: []
    },
    // conflicted position
    {
      qid: 'Q555777',
      name: 'Mayor of Test City',
      statements: [
        {
          id: 'pos-conflicted',
          statement_id: null,
          start_date: '2020-01-01',
          start_date_precision: 9,
          end_date: '2024-01-01',
          end_date_precision: 9,
          proof_line: 'served as mayor from 2020 to 2024',
          archived_page: mockArchivedPage,
        }
      ]
    },
    // extracted-only position
    {
      qid: 'Q777888',
      name: 'Council Member',
      statements: [
        {
          id: 'pos-extracted',
          statement_id: null,
          start_date: '2018-01-01',
          start_date_precision: 9,
          end_date: null,
          end_date_precision: null,
          proof_line: 'council member since 2018',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
  birthplaces: [
    // existing-only birthplace
    {
      qid: 'Q333444',
      name: 'Old City',
      statements: []
    },
    // conflicted birthplace
    {
      qid: 'Q123456',
      name: 'Test City',
      statements: [
        {
          id: 'birth-conflicted',
          statement_id: null,
          proof_line: 'was born in Test City',
          archived_page: mockArchivedPage,
        }
      ]
    },
    // extracted-only birthplace
    {
      qid: 'Q999000',
      name: 'New City',
      statements: [
        {
          id: 'birth-extracted',
          statement_id: null,
          proof_line: 'was born in New City',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
};

export const mockPoliticianExtractedOnly: Politician = {
  id: 'pol-extracted',
  name: 'Extracted Only Politician',
  wikidata_id: 'Q333444',
  properties: [
    {
      type: 'birth_date',
      statements: [
        {
          id: 'prop-extracted-only-1',
          statement_id: null,
          value: '1980-05-15',
          value_precision: 9,
          proof_line: 'born on May 15, 1980',
          archived_page: mockArchivedPage,
        }
      ]
    },
    {
      type: 'nationality',
      statements: [
        {
          id: 'prop-extracted-only-2',
          statement_id: null,
          value: 'German',
          value_precision: null,
          proof_line: 'German citizen',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
  positions: [
    {
      qid: 'Q111222',
      name: 'Minister of Education',
      statements: [
        {
          id: 'pos-extracted-only-1',
          statement_id: null,
          start_date: '2019-01-01',
          start_date_precision: 9,
          end_date: '2023-01-01',
          end_date_precision: 9,
          proof_line: 'served as minister from 2019 to 2023',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
  birthplaces: [
    {
      qid: 'Q555666',
      name: 'Berlin',
      statements: [
        {
          id: 'birth-extracted-only-1',
          statement_id: null,
          proof_line: 'was born in Berlin',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
};

export const mockPoliticianExistingOnly: Politician = {
  id: 'pol-existing',
  name: 'Existing Only Politician',
  wikidata_id: 'Q555666',
  properties: [
    {
      type: 'birth_date',
      statements: [] // Empty statements = existing only in Wikidata
    },
    {
      type: 'death_date',
      statements: []
    }
  ],
  positions: [
    {
      qid: 'Q777888',
      name: 'Prime Minister',
      statements: []
    },
    {
      qid: 'Q999000',
      name: 'Parliament Member',
      statements: []
    }
  ],
  birthplaces: [
    {
      qid: 'Q111333',
      name: 'Capital City',
      statements: []
    }
  ],
};

// Mock politician that demonstrates the edge case: statement with both statement_id and archived_page
// In this case, archived_page should be hidden since statement_id indicates it's a Wikidata statement
export const mockPoliticianWithEdgeCases: Politician = {
  id: 'pol-edge-cases',
  name: 'Edge Case Politician',
  wikidata_id: 'Q777888',
  properties: [
    {
      type: 'birth_date',
      statements: [
        // Wikidata statement with statement_id (extracted statement should be hidden)
        {
          id: 'prop-wikidata-1',
          statement_id: 'Q777888$12345678-1234-1234-1234-123456789012',
          value: '1980-01-01',
          value_precision: 9,
          proof_line: 'born on January 1, 1980',
          archived_page: mockArchivedPage, // This should be hidden because statement_id exists
        },
        // Regular extracted statement
        {
          id: 'prop-extracted-1',
          statement_id: null,
          value: '1980-01-02',
          value_precision: 9,
          proof_line: 'born on January 2, 1980',
          archived_page: mockArchivedPage,
        }
      ]
    }
  ],
  positions: [
    {
      qid: 'Q123456',
      name: 'Mayor',
      statements: [
        // Wikidata statement with statement_id
        {
          id: 'pos-wikidata-1',
          statement_id: 'Q123456$87654321-4321-4321-4321-210987654321',
          start_date: '2020-01-01',
          start_date_precision: 9,
          end_date: '2024-01-01',
          end_date_precision: 9,
          proof_line: 'served as mayor from 2020 to 2024',
          archived_page: mockArchivedPage, // This should be hidden
        }
      ]
    }
  ],
  birthplaces: [
    {
      qid: 'Q987654',
      name: 'Test City',
      statements: [
        // Wikidata statement with statement_id
        {
          id: 'birth-wikidata-1',
          statement_id: 'Q987654$11111111-2222-3333-4444-555555555555',
          proof_line: 'was born in Test City',
          archived_page: mockArchivedPage, // This should be hidden
        }
      ]
    }
  ],
};