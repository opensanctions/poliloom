import {
  SourceResponse,
  Politician,
  Property,
  PropertyReference,
  PropertyType,
  EntityPropertyType,
  SearchFn,
  SearchEntity,
} from '@/types'

export const TUTORIAL_PAGE_IDS = ['tutorial-page-1', 'tutorial-page-2', 'tutorial-page-3'] as const

// Shared sources
const page1: SourceResponse = {
  id: 'tutorial-page-1',
  url: 'https://example.parliament.gov/members/jane-doe',
  url_hash: 'tutorial-hash-1',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
}

const page2: SourceResponse = {
  id: 'tutorial-page-2',
  url: 'https://en.wikipedia.org/wiki/Jane_Doe_(politician)',
  url_hash: 'tutorial-hash-2',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
}

const page3: SourceResponse = {
  id: 'tutorial-page-3',
  url: 'https://parliament.springfield.gov/members',
  url_hash: 'tutorial-hash-3',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
}

export const tutorialSources = { page1, page2, page3 }

function ref(id: string, source: SourceResponse, quotes: string[]): PropertyReference {
  return { id, source, supporting_quotes: quotes }
}

// Shared politician identity
const politicianBase = {
  id: 'tutorial-politician',
  name: 'Jane Doe',
  wikidata_id: 'Q955672',
  sources: [page1, page2] as SourceResponse[],
} as const satisfies Pick<Politician, 'id' | 'name' | 'wikidata_id' | 'sources'>

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
  sources: [
    ref('ref-tutorial-1', page1, [
      'Jane Doe was born on March 15, 1975 in Springfield.',
      'Born: March 15, 1975',
    ]),
  ],
}

// --- Step politicians ---

export const extractedDataPolitician: Politician = {
  ...politicianBase,
  sources: [page1],
  properties: [
    birthDate,
    {
      id: 'tutorial-existing-position',
      type: PropertyType.P39,
      entity_id: 'Q486839',
      entity_name: 'Member of Parliament',
      statement_id: 'Q955672$existing-statement-1',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      sources: [],
    },
  ],
}

export const birthDatePolitician: Politician = {
  ...politicianBase,
  sources: [page1],
  properties: [
    {
      id: 'tutorial-birth-date-incorrect',
      type: PropertyType.P569,
      value: '+1952-06-08T00:00:00Z',
      value_precision: 11,
      sources: [
        ref('ref-tutorial-2', page1, [
          'Following in the footsteps of her mother Mary Doe (born June 8, 1952), she pursued a career in public service.',
        ]),
      ],
    },
    {
      ...birthDate,
      sources: [ref('ref-tutorial-3', page1, birthDate.sources[0].supporting_quotes!)],
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
      sources: [ref('ref-tutorial-4', page1, springfieldMemberQuotes)],
    },
    {
      id: 'tutorial-position-2',
      type: PropertyType.P39,
      entity_id: 'Q4018482',
      entity_name: 'Minister of Education',
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2022-06-01T00:00:00Z', precision: 10 } } }],
      },
      sources: [
        {
          id: 'ref-tutorial-5',
          source: page2,
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
  sources: [page1],
  properties: [
    {
      id: 'tutorial-existing-specific-position',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      statement_id: 'Q955672$existing-specific-1',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      sources: [],
    },
    {
      id: 'tutorial-generic-position',
      type: PropertyType.P39,
      entity_id: 'Q486839',
      entity_name: 'Member of Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      sources: [ref('ref-tutorial-6', page1, springfieldMemberQuotes)],
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
      sources: [],
    },
    {
      id: 'tutorial-new-specific-position',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      sources: [ref('ref-tutorial-7', page1, springfieldMemberQuotes)],
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
      sources: [],
    },
    {
      id: 'tutorial-new-specific-with-source',
      type: PropertyType.P39,
      entity_id: 'Q1343573',
      entity_name: 'Member of Springfield Parliament',
      qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
      sources: [ref('ref-tutorial-8', page1, springfieldMemberQuotes)],
    },
  ],
}

// --- Add new data tutorial ---

export const addNewDataPolitician: Politician = {
  ...politicianBase,
  sources: [page3],
  properties: [
    {
      ...birthDate,
      sources: [
        ref('ref-tutorial-9', page3, ['Jane Doe was born on March 15, 1975 in Springfield.']),
      ],
    },
  ],
}

const TUTORIAL_POSITIONS: SearchEntity[] = [
  {
    wikidata_id: 'Q1343573',
    name: 'Member of Springfield Parliament',
    description: 'member of the Springfield Parliament',
  },
  {
    wikidata_id: 'Q486839',
    name: 'Member of Parliament',
    description: 'member of a parliament',
  },
  {
    wikidata_id: 'Q999002',
    name: 'Mayor of Springfield',
    description: 'head of government of Springfield',
  },
]

const tutorialPositionSearch: SearchFn = async (query: string) => {
  const lower = query.toLowerCase()
  return TUTORIAL_POSITIONS.filter(
    (p) =>
      p.name.toLowerCase().includes(lower) ||
      (p.description?.toLowerCase().includes(lower) ?? false),
  )
}

const emptySearch: SearchFn = async () => []

export const tutorialEntitySearches: Record<EntityPropertyType, SearchFn> = {
  [PropertyType.P39]: tutorialPositionSearch,
  [PropertyType.P19]: emptySearch,
  [PropertyType.P27]: emptySearch,
}
