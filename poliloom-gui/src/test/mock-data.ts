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