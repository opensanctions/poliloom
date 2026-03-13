import {
  ArchivedPageResponse,
  Politician,
  Property,
  PropertyReference,
  PropertyType,
} from '@/types'

// Shared archived pages
const page1: ArchivedPageResponse = {
  id: 'tutorial-page-1',
  url: 'https://example.parliament.gov/members/jane-doe',
  content_hash: 'tutorial-hash-1',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
}

const page2: ArchivedPageResponse = {
  id: 'tutorial-page-2',
  url: 'https://en.wikipedia.org/wiki/Jane_Doe_(politician)',
  content_hash: 'tutorial-hash-2',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
}

export const archivedPages = { page1, page2 }

// Helper to create a reference to page1
function ref(id: string, quotes: string[]): PropertyReference {
  return { id, archived_page_id: page1.id, supporting_quotes: quotes }
}

// Shared politician identity
const politicianBase = {
  id: 'tutorial-politician',
  name: 'Jane Doe',
  wikidata_id: 'Q955672',
  archived_pages: [page1, page2] as ArchivedPageResponse[],
} as const satisfies Pick<Politician, 'id' | 'name' | 'wikidata_id' | 'archived_pages'>

// Reusable qualifier snippet
function startDate(time: string, precision: number) {
  return { P580: [{ datavalue: { value: { time, precision } } }] }
}

// --- Shared properties ---

const springfieldMemberQuotes = [
  'Jane Doe has been a Member of the Springfield Parliament since January 2020.',
  'Elected to Springfield Parliament in 2020',
]

const birthDate: Property = {
  id: 'tutorial-birth-date',
  type: PropertyType.P569,
  value: '+1975-03-15T00:00:00Z',
  value_precision: 11,
  archived_pages: [
    ref('ref-tutorial-1', [
      'Jane Doe was born on March 15, 1975 in Springfield.',
      'Born: March 15, 1975',
    ]),
  ],
}

// --- Step politicians ---

export const extractedDataPolitician: Politician = {
  ...politicianBase,
  properties: [
    birthDate,
    {
      id: 'tutorial-existing-position',
      type: PropertyType.P39,
      entity_id: 'Q486839',
      entity_name: 'Member of Parliament',
      statement_id: 'Q955672$existing-statement-1',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      archived_pages: [],
    },
  ],
}

export const birthDatePolitician: Politician = {
  ...politicianBase,
  properties: [
    {
      id: 'tutorial-birth-date-incorrect',
      type: PropertyType.P569,
      value: '+1952-06-08T00:00:00Z',
      value_precision: 11,
      archived_pages: [
        ref('ref-tutorial-2', [
          'Following in the footsteps of her mother Mary Doe (born June 8, 1952), she pursued a career in public service.',
        ]),
      ],
    },
    {
      ...birthDate,
      archived_pages: [ref('ref-tutorial-3', birthDate.archived_pages[0].supporting_quotes!)],
    },
  ],
}

export const multipleSourcesPolitician: Politician = {
  ...politicianBase,
  properties: [
    {
      id: 'tutorial-position-1',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      archived_pages: [ref('ref-tutorial-4', springfieldMemberQuotes)],
    },
    {
      id: 'tutorial-position-2',
      type: PropertyType.P39,
      entity_id: 'Q4018482',
      entity_name: 'Minister of Education',
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2022-06-01T00:00:00Z', precision: 10 } } }],
      },
      archived_pages: [
        {
          id: 'ref-tutorial-5',
          archived_page_id: page2.id,
          supporting_quotes: [
            'She was appointed Minister of Education in June 2022.',
            'Current Minister of Education since 2022',
          ],
        },
      ],
    },
  ],
}

export const genericVsSpecificPolitician: Politician = {
  ...politicianBase,
  properties: [
    {
      id: 'tutorial-existing-specific-position',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      statement_id: 'Q955672$existing-specific-1',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      archived_pages: [],
    },
    {
      id: 'tutorial-generic-position',
      type: PropertyType.P39,
      entity_id: 'Q486839',
      entity_name: 'Member of Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      archived_pages: [ref('ref-tutorial-6', springfieldMemberQuotes)],
    },
  ],
}

export const deprecateSimplePolitician: Politician = {
  ...politicianBase,
  properties: [
    {
      id: 'tutorial-existing-generic-no-metadata',
      type: PropertyType.P39,
      entity_id: 'Q486839',
      entity_name: 'Member of Parliament',
      statement_id: 'Q955672$existing-generic-1',
      archived_pages: [],
    },
    {
      id: 'tutorial-new-specific-position',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      archived_pages: [ref('ref-tutorial-7', springfieldMemberQuotes)],
    },
  ],
}

export const deprecateWithMetadataPolitician: Politician = {
  ...politicianBase,
  properties: [
    {
      id: 'tutorial-existing-with-metadata',
      type: PropertyType.P39,
      entity_id: 'Q486839',
      entity_name: 'Member of Parliament',
      statement_id: 'Q955672$existing-with-refs-1',
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P768: [
          {
            datavalue: {
              value: { 'entity-type': 'item', id: 'Q7580930', 'numeric-id': 7580930 } as never,
            },
          },
        ],
        P2937: [
          {
            datavalue: {
              value: { 'entity-type': 'item', id: 'Q72127378', 'numeric-id': 72127378 } as never,
            },
          },
        ],
      },
      references: [
        {
          P854: [{ datavalue: { value: 'https://parliament.gov/elections/2020/results' } }],
          P813: [{ datavalue: { value: { time: '+2020-02-15T00:00:00Z', precision: 11 } } }],
          P1476: [
            { datavalue: { value: { text: 'Official Election Results 2020', language: 'en' } } },
          ],
        },
        {
          P854: [
            { datavalue: { value: 'https://news.example.com/politics/election-winners-2020' } },
          ],
          P813: [{ datavalue: { value: { time: '+2020-01-05T00:00:00Z', precision: 11 } } }],
          P1476: [{ datavalue: { value: { text: 'Election Winners Announced', language: 'en' } } }],
        },
      ],
      archived_pages: [],
    },
    {
      id: 'tutorial-new-specific-with-source',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      archived_pages: [ref('ref-tutorial-8', springfieldMemberQuotes)],
    },
  ],
}
