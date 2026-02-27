import { Politician, PropertyType, ArchivedPageResponse, SourceResponse } from '@/types'

const mockArchivedPage: ArchivedPageResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  content_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
}

const mockArchivedPage2: ArchivedPageResponse = {
  id: 'archived-2',
  url: 'https://government.example.com/officials/test-politician',
  content_hash: 'def456',
  fetch_timestamp: '2024-02-15T00:00:00Z',
}

const mockArchivedPage3: ArchivedPageResponse = {
  id: 'archived-3',
  url: 'https://news.example.com/article/politician-bio',
  content_hash: 'ghi789',
  fetch_timestamp: '2024-03-20T00:00:00Z',
}

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
      sources: [
        {
          id: 'ref-1',
          archived_page: mockArchivedPage,
          supporting_quotes: ['born on January 1, 1970'],
        },
      ],
    },
    {
      id: 'pos-1',
      type: PropertyType.P39,
      entity_id: 'Q555777',
      entity_name: 'Mayor of Test City',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-2',
          archived_page: mockArchivedPage,
          supporting_quotes: ['served as mayor from 2020 to 2024'],
        },
      ],
    },
    {
      id: 'birth-1',
      type: PropertyType.P19,
      entity_id: 'Q123456',
      entity_name: 'Test City',
      statement_id: null,
      sources: [
        {
          id: 'ref-3',
          archived_page: mockArchivedPage,
          supporting_quotes: ['was born in Test City'],
        },
      ],
    },
  ],
}

export const mockEmptyPolitician: Politician = {
  id: 'pol-2',
  name: 'Empty Politician',
  wikidata_id: null,
  properties: [],
}

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
      sources: [
        {
          id: 'ref-conflicted',
          archived_page: mockArchivedPage,
          supporting_quotes: ['born on January 2, 1970'],
        },
      ],
    },
    // Citizenship (extracted-only)
    {
      id: 'prop-extracted',
      type: PropertyType.P27,
      entity_id: 'Q142',
      entity_name: 'France',
      statement_id: null,
      sources: [
        {
          id: 'ref-extracted',
          archived_page: mockArchivedPage,
          supporting_quotes: ['French politician'],
        },
      ],
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
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-pos-conflicted',
          archived_page: mockArchivedPage,
          supporting_quotes: ['served as mayor from 2020 to 2024'],
        },
      ],
    },
    // Position (extracted-only)
    {
      id: 'pos-extracted',
      type: PropertyType.P39,
      entity_id: 'Q777888',
      entity_name: 'Council Member',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2018-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-pos-extracted',
          archived_page: mockArchivedPage,
          supporting_quotes: ['council member since 2018'],
        },
      ],
    },
    // Birthplace (conflicted)
    {
      id: 'birth-conflicted',
      type: PropertyType.P19,
      entity_id: 'Q123456',
      entity_name: 'Test City',
      statement_id: null,
      sources: [
        {
          id: 'ref-birth-conflicted',
          archived_page: mockArchivedPage,
          supporting_quotes: ['was born in Test City'],
        },
      ],
    },
    // Birthplace (extracted-only)
    {
      id: 'birth-extracted',
      type: PropertyType.P19,
      entity_id: 'Q999000',
      entity_name: 'New City',
      statement_id: null,
      sources: [
        {
          id: 'ref-birth-extracted',
          archived_page: mockArchivedPage,
          supporting_quotes: ['was born in New City'],
        },
      ],
    },
  ],
}

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
      sources: [
        {
          id: 'ref-eo-1',
          archived_page: mockArchivedPage,
          supporting_quotes: ['born on May 15, 1980'],
        },
      ],
    },
    {
      id: 'prop-extracted-only-2',
      type: PropertyType.P27,
      entity_id: 'Q183',
      entity_name: 'Germany',
      statement_id: null,
      sources: [
        {
          id: 'ref-eo-2',
          archived_page: mockArchivedPage,
          supporting_quotes: ['German citizen'],
        },
      ],
    },
    {
      id: 'pos-extracted-only-1',
      type: PropertyType.P39,
      entity_id: 'Q111222',
      entity_name: 'Minister of Education',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2019-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2023-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-eo-3',
          archived_page: mockArchivedPage,
          supporting_quotes: ['served as minister from 2019 to 2023'],
        },
      ],
    },
    {
      id: 'birth-extracted-only-1',
      type: PropertyType.P19,
      entity_id: 'Q64',
      entity_name: 'Berlin',
      statement_id: null,
      sources: [
        {
          id: 'ref-eo-4',
          archived_page: mockArchivedPage,
          supporting_quotes: ['was born in Berlin'],
        },
      ],
    },
  ],
}

export const mockPoliticianExistingOnly: Politician = {
  id: 'pol-existing',
  name: 'Existing Only Politician',
  wikidata_id: 'Q555666',
  properties: [], // No unevaluated properties - everything exists in Wikidata already
}

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
      sources: [
        {
          id: 'ref-edge-1',
          archived_page: mockArchivedPage,
          supporting_quotes: ['born on January 1, 1980'],
        },
      ],
    },
    // Regular extracted statement
    {
      id: 'prop-extracted-1',
      type: PropertyType.P569,
      value: '+1980-01-02T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [
        {
          id: 'ref-edge-2',
          archived_page: mockArchivedPage,
          supporting_quotes: ['born on January 2, 1980'],
        },
      ],
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
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [],
    },
    // Wikidata birthplace statement
    {
      id: 'birth-wikidata-1',
      type: PropertyType.P19,
      entity_id: 'Q987654',
      entity_name: 'Test City',
      statement_id: 'Q987654$11111111-2222-3333-4444-555555555555',
      sources: [],
    },
  ],
}

// Mock politician with different archived pages for testing View button switching
export const mockPoliticianWithDifferentSources: Politician = {
  id: 'pol-different-sources',
  name: 'Multi-Source Politician',
  wikidata_id: 'Q999888',
  properties: [
    {
      id: 'prop-source-1',
      type: PropertyType.P569,
      value: '+1975-06-15T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [
        {
          id: 'ref-src-1',
          archived_page: mockArchivedPage, // archived-1
          supporting_quotes: ['born on June 15, 1975'],
        },
      ],
    },
    {
      id: 'pos-source-2',
      type: PropertyType.P39,
      entity_id: 'Q444555',
      entity_name: 'Governor',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2018-01-01T00:00:00Z', precision: 11 } } }],
      },
      sources: [
        {
          id: 'ref-src-2',
          archived_page: mockArchivedPage2, // archived-2
          supporting_quotes: ['elected governor in 2018'],
        },
      ],
    },
    {
      id: 'birth-source-3',
      type: PropertyType.P19,
      entity_id: 'Q666777',
      entity_name: 'Capital City',
      statement_id: null,
      sources: [
        {
          id: 'ref-src-3',
          archived_page: mockArchivedPage3, // archived-3
          supporting_quotes: ['was born in Capital City'],
        },
      ],
    },
  ],
}

// Source-centric mock: one archived page, multiple politicians
export const mockSourceResponse: SourceResponse = {
  archived_page: mockArchivedPage,
  politicians: [
    {
      id: 'pol-src-1',
      name: 'Source Politician A',
      wikidata_id: 'Q111000',
      properties: [
        {
          id: 'src-prop-1',
          type: PropertyType.P569,
          value: '+1970-01-01T00:00:00Z',
          value_precision: 11,
          statement_id: null,
          sources: [
            {
              id: 'src-ref-1',
              archived_page: mockArchivedPage,
              supporting_quotes: ['born on January 1, 1970'],
            },
          ],
        },
        {
          id: 'src-prop-2',
          type: PropertyType.P39,
          entity_id: 'Q555777',
          entity_name: 'Mayor of Test City',
          statement_id: null,
          sources: [
            {
              id: 'src-ref-2',
              archived_page: mockArchivedPage,
              supporting_quotes: ['served as mayor'],
            },
          ],
        },
      ],
    },
    {
      id: 'pol-src-2',
      name: 'Source Politician B',
      wikidata_id: 'Q222000',
      properties: [
        {
          id: 'src-prop-3',
          type: PropertyType.P27,
          entity_id: 'Q142',
          entity_name: 'France',
          statement_id: null,
          sources: [
            {
              id: 'src-ref-3',
              archived_page: mockArchivedPage,
              supporting_quotes: ['French citizen'],
            },
          ],
        },
      ],
    },
  ],
}

// Export archived pages for tests
export { mockArchivedPage, mockArchivedPage2, mockArchivedPage3 }
