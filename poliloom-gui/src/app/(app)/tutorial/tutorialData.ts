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

// Tutorial steps as an enum so we can reorder/insert without renumbering
export enum TutorialStep {
  // Basic tutorial
  Welcome,
  WhyYourHelpMatters,
  SourceDocuments,
  SourcesAndAddSource,
  ExtractedData,
  GiveItATry,
  BirthDateEvaluation,
  MultipleSources,
  MultipleSourcesEvaluation,
  SpecificOverGeneric,
  SpecificOverGenericEvaluation,
  BasicKeyTakeaways,
  // Advanced tutorial
  AdvancedWelcome,
  AddingNewData,
  AddNewDataEvaluation,
  ReplacingGenericData,
  DeprecateSimpleEvaluation,
  DataWithMetadata,
  DataWithMetadataEvaluation,
  AdvancedKeyTakeaways,
}

// Tutorial-specific property with expected evaluation outcome
export interface TutorialProperty extends Property {
  /** Expected evaluation: true = accept/keep, false = reject/deprecate */
  expectedEvaluation?: boolean
  /** Must the user explicitly act before submit is enabled? Defaults to true. */
  required?: boolean
}

// Data for each interactive evaluation step
export interface TutorialEvaluationStep {
  politician: Omit<Politician, 'properties'> & { properties: TutorialProperty[] }
  expectedCreates?: { type: string; entity_id: string }[]
  entitySearches?: Record<EntityPropertyType, SearchFn>
  isAdvancedMode: boolean
  backStep: TutorialStep
  success: { title: string; message: string }
  error: { title: string; message: string; hint: string }
}

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

// --- Non-interactive step data ---

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

// --- Tutorial entity searches ---

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

const tutorialEntitySearches: Record<EntityPropertyType, SearchFn> = {
  [PropertyType.P39]: tutorialPositionSearch,
  [PropertyType.P19]: emptySearch,
  [PropertyType.P27]: emptySearch,
}

// --- Interactive evaluation steps keyed by tutorial step ---

export const tutorialEvaluationSteps: Partial<Record<TutorialStep, TutorialEvaluationStep>> = {
  [TutorialStep.BirthDateEvaluation]: {
    politician: {
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
          expectedEvaluation: false, // Reject - June 8, 1952 is the mother's birth date
        },
        {
          ...birthDate,
          sources: [ref('ref-tutorial-3', page1, birthDate.sources[0].supporting_quotes!)],
          expectedEvaluation: true, // Accept - March 15, 1975 is correct
        },
      ],
    },
    isAdvancedMode: false,
    backStep: TutorialStep.GiveItATry,
    success: {
      title: 'Excellent!',
      message:
        "You correctly identified that March 15, 1975 matches the source, while June 8, 1952 was actually the mother's birth date. Reading carefully makes all the difference!",
    },
    error: {
      title: 'Not Quite Right',
      message:
        'Take another look at the source document. One birth date belongs to Jane Doe, and the other belongs to someone else mentioned in the text.',
      hint: 'Hint: Look carefully at who each date refers to in the source text.',
    },
  },

  [TutorialStep.MultipleSourcesEvaluation]: {
    politician: {
      ...politicianBase,
      properties: [
        {
          id: 'tutorial-position-1',
          type: PropertyType.P39,
          entity_id: 'Q1343573',
          entity_name: 'Member of Springfield Parliament',
          qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
          sources: [ref('ref-tutorial-4', page1, springfieldMemberQuotes)],
          expectedEvaluation: true, // Accept - Member of Parliament
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
          expectedEvaluation: true, // Accept - Minister of Education
        },
      ],
    },
    isAdvancedMode: false,
    backStep: TutorialStep.MultipleSources,
    success: {
      title: 'Great Job!',
      message:
        'You correctly verified both positions from their respective source documents. Being able to work with multiple sources is an important skill!',
    },
    error: {
      title: "Let's Try Again",
      message:
        'Make sure to check each position against its source document. Click "View" to switch between sources and verify each extraction.',
      hint: "Hint: Read each source carefully — does the extracted data match what's written?",
    },
  },

  [TutorialStep.SpecificOverGenericEvaluation]: {
    politician: {
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
          expectedEvaluation: true, // Keep - specific position already exists
          required: false,
        },
        {
          id: 'tutorial-generic-position',
          type: PropertyType.P39,
          entity_id: 'Q486839',
          entity_name: 'Member of Parliament',
          qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
          sources: [ref('ref-tutorial-6', page1, springfieldMemberQuotes)],
          expectedEvaluation: false, // Reject - generic when specific exists
        },
      ],
    },
    isAdvancedMode: false,
    backStep: TutorialStep.SpecificOverGeneric,
    success: {
      title: 'Perfect!',
      message:
        'You correctly rejected the generic "Member of Parliament" because the more specific "Member of Springfield Parliament" already exists. Quality over quantity!',
    },
    error: {
      title: 'Almost There',
      message:
        "Remember: when we already have specific data, we don't need a generic version. Look at what data already exists before accepting new extractions.",
      hint: 'Hint: "Member of Springfield Parliament" is more specific than "Member of Parliament".',
    },
  },

  [TutorialStep.AddNewDataEvaluation]: {
    politician: {
      ...politicianBase,
      sources: [page3],
      properties: [
        {
          ...birthDate,
          sources: [
            ref('ref-tutorial-9', page3, [
              'Jane Doe Springfield Central Democratic Alliance March 15, 1975',
            ]),
          ],
          expectedEvaluation: true, // Keep - the existing birth date is correct
          required: false,
        },
      ],
    },
    expectedCreates: [{ type: PropertyType.P39, entity_id: 'Q1343573' }],
    entitySearches: tutorialEntitySearches,
    isAdvancedMode: true,
    backStep: TutorialStep.AddingNewData,
    success: {
      title: 'Nice Work!',
      message:
        'You correctly identified that Jane Doe is a "Member of Springfield Parliament" and added it as new data. This is how you can fill in gaps in the extracted data!',
    },
    error: {
      title: 'Not Quite Right',
      message:
        "Check the source document — it's a directory of Springfield Parliament members. Jane Doe needs a position that matches.",
      hint: 'Hint: Look at the page title — what role do all the people listed there share?',
    },
  },

  [TutorialStep.DeprecateSimpleEvaluation]: {
    politician: {
      ...politicianBase,
      properties: [
        {
          id: 'tutorial-existing-generic-no-metadata',
          type: PropertyType.P39,
          entity_id: 'Q486839',
          entity_name: 'Member of Parliament',
          statement_id: 'Q955672$existing-generic-1',
          sources: [],
          expectedEvaluation: false, // Deprecate - generic with no metadata
          required: false,
        },
        {
          id: 'tutorial-new-specific-position',
          type: PropertyType.P39,
          entity_id: 'Q1343573',
          entity_name: 'Member of Springfield Parliament',
          qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
          sources: [ref('ref-tutorial-7', page1, springfieldMemberQuotes)],
          expectedEvaluation: true, // Accept - specific replacement
        },
      ],
    },
    isAdvancedMode: true,
    backStep: TutorialStep.ReplacingGenericData,
    success: {
      title: 'Well Done!',
      message:
        'You correctly deprecated the generic "Member of Parliament" and accepted the more specific "Member of Springfield Parliament". Nice work!',
    },
    error: {
      title: 'Not Quite Right',
      message:
        'The existing "Member of Parliament" is generic. The new extraction gives us more specific information - deprecate the old and accept the new.',
      hint: 'Hint: Is "Member of Parliament" adding anything that "Member of Springfield Parliament" doesn\'t already cover?',
    },
  },

  [TutorialStep.DataWithMetadataEvaluation]: {
    politician: {
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
                  value: {
                    'entity-type': 'item',
                    id: 'Q72127378',
                    'numeric-id': 72127378,
                  } as never,
                },
              },
            ],
          },
          references: [
            {
              P854: [{ datavalue: { value: 'https://parliament.gov/elections/2020/results' } }],
              P813: [{ datavalue: { value: { time: '+2020-02-15T00:00:00Z', precision: 11 } } }],
              P1476: [
                {
                  datavalue: { value: { text: 'Official Election Results 2020', language: 'en' } },
                },
              ],
            },
            {
              P854: [
                { datavalue: { value: 'https://news.example.com/politics/election-winners-2020' } },
              ],
              P813: [{ datavalue: { value: { time: '+2020-01-05T00:00:00Z', precision: 11 } } }],
              P1476: [
                { datavalue: { value: { text: 'Election Winners Announced', language: 'en' } } },
              ],
            },
          ],
          sources: [],
          expectedEvaluation: true, // Keep - don't deprecate (metadata is valuable)
          required: false,
        },
        {
          id: 'tutorial-new-specific-with-source',
          type: PropertyType.P39,
          entity_id: 'Q1343573',
          entity_name: 'Member of Springfield Parliament',
          qualifiers: startDate('+2020-01-01T00:00:00Z', 11),
          sources: [ref('ref-tutorial-8', page1, springfieldMemberQuotes)],
          expectedEvaluation: true, // Accept the new specific data
        },
      ],
    },
    isAdvancedMode: true,
    backStep: TutorialStep.DataWithMetadata,
    success: {
      title: 'Great Choice!',
      message:
        'You accepted the new specific data and kept the existing data with its valuable metadata. Well done!',
    },
    error: {
      title: "Let's Reconsider",
      message:
        'The new data is good, but the existing data has rich metadata attached. Deprecating it means losing all of that.',
      hint: 'Hint: Notice the references and qualifiers on the existing data — what happens to those if you deprecate it?',
    },
  },
}
