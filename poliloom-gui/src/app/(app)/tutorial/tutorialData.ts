import {
  Action,
  ActionEvidence,
  JsonPatchOperation,
  Politician,
  RestSnak,
  RestStatement,
  RestTimeValue,
  RestValue,
  SourceResponse,
  Statement,
  TermMaps,
} from '@/types'

// Tutorial steps as an enum so we can reorder/insert without renumbering
export enum TutorialStep {
  // Basic tutorial
  Welcome,
  WhyYourHelpMatters,
  SourceDocuments,
  LinkedSources,
  ExtractedData,
  GiveItATry,
  BirthDateDecisions,
  MultipleSources,
  MultipleSourcesDecisions,
  SpecificOverGeneric,
  SpecificOverGenericDecisions,
  BasicKeyTakeaways,
  // Advanced tutorial
  AdvancedWelcome,
  RefiningValues,
  RefiningValuesDecisions,
  CompletingTimeframes,
  CompletingTimeframesDecisions,
  AddingReferences,
  AddingReferencesDecisions,
  AdvancedKeyTakeaways,
}

/** Data for each interactive review step */
export interface TutorialReviewStep {
  politician: Politician
  /** Expected decision per action id: true = accept, false = discard */
  expectedDecisions: Record<string, boolean>
  backStep: TutorialStep
  success: { title: string; message: string }
  error: { title: string; message: string; hint: string }
}

export const TUTORIAL_PAGE_IDS = ['tutorial-page-1', 'tutorial-page-2', 'tutorial-page-3'] as const

// --- Fixture builders (mirror the backend REST statement shape) ---

const terms = (labels: Record<string, string>): TermMaps => ({
  labels,
  descriptions: {},
  aliases: {},
})

const timeContent = (time: string, precision: number): RestTimeValue => ({
  time,
  precision,
  calendarmodel: 'http://www.wikidata.org/entity/Q1985727',
})

const timeValue = (time: string, precision: number): RestValue => ({
  type: 'value',
  content: timeContent(time, precision),
})

const entityValue = (qid: string): RestValue => ({ type: 'value', content: qid })

const startTimeQualifier = (time: string, precision: number): RestSnak => ({
  property: { id: 'P580' },
  value: timeValue(time, precision),
})

function statement(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    qualifiers?: RestSnak[]
    references?: RestStatement['references']
    entityTerms?: TermMaps | null
  } = {},
): Statement {
  return {
    id,
    document: {
      id,
      rank: 'normal',
      property: { id: propertyId },
      value,
      qualifiers: options.qualifiers ?? [],
      references: options.references ?? [],
    },
    entity_terms: options.entityTerms ?? null,
  }
}

function evidence(id: string, source: SourceResponse, supportingQuotes: string[]): ActionEvidence {
  return { id, source, supporting_quotes: supportingQuotes }
}

function createAction(
  id: string,
  propertyId: string,
  value: RestValue,
  actionEvidence: ActionEvidence[],
  options: { qualifiers?: RestSnak[]; entityTerms?: TermMaps | null } = {},
): Action {
  return {
    id,
    kind: 'CREATE_STATEMENT',
    statement_id: null,
    payload: {
      statement: {
        rank: 'normal',
        property: { id: propertyId },
        value,
        qualifiers: options.qualifiers ?? [],
        references: [],
      },
    },
    entity_terms: options.entityTerms ?? null,
    evidence: actionEvidence,
    is_accepted: null,
    applied_at: null,
    error: null,
  }
}

function editAction(
  id: string,
  statementId: string,
  patch: JsonPatchOperation[],
  actionEvidence: ActionEvidence[] = [],
  options: { entityTerms?: TermMaps | null } = {},
): Action {
  return {
    id,
    kind: 'EDIT_STATEMENT',
    statement_id: statementId,
    payload: { patch },
    entity_terms: options.entityTerms ?? null,
    evidence: actionEvidence,
    is_accepted: null,
    applied_at: null,
    error: null,
  }
}

// --- Shared sources ---

const page1: SourceResponse = {
  id: 'tutorial-page-1',
  url: 'https://example.parliament.gov/members/jane-doe',
  url_hash: 'tutorial-hash-1',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
  language_qids: [],
}

const page2: SourceResponse = {
  id: 'tutorial-page-2',
  url: 'https://en.wikipedia.org/wiki/Jane_Doe_(politician)',
  url_hash: 'tutorial-hash-2',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
  language_qids: [],
}

const page3: SourceResponse = {
  id: 'tutorial-page-3',
  url: 'https://parliament.springfield.gov/members',
  url_hash: 'tutorial-hash-3',
  fetch_timestamp: '2024-01-15T10:00:00Z',
  status: 'done',
  language_qids: [],
}

export const tutorialSources = { page1, page2, page3 }

// --- Shared entities and evidence ---

const springfieldParliament = terms({ en: 'Member of Springfield Parliament' })
const memberOfParliament = terms({ en: 'Member of Parliament' })
const ministerOfEducation = terms({ en: 'Minister of Education' })
const springfieldCity = terms({ en: 'Springfield' })
const springfieldRepublic = terms({ en: 'Springfield Republic' })

const springfieldMemberQuotes = [
  'Jane Doe has been a Member of the Springfield Parliament since January 2020.',
  'Elected to Springfield Parliament in 2020',
]

const birthDateQuotes = [
  'Jane Doe was born on March 15, 1975 in Springfield.',
  'Born: March 15, 1975',
]

// Shared politician identity
const politicianBase = {
  wikidata_id: 'Q955672',
  terms: terms({ en: 'Jane Doe' }),
} as const satisfies Pick<Politician, 'wikidata_id' | 'terms'>

// --- Non-interactive step data ---

export const extractedDataPolitician: Politician = {
  id: 'tutorial-politician-extracted-data',
  ...politicianBase,
  sources: [page1],
  statements: [
    statement('Q955672$springfield-member', 'P39', entityValue('Q1343573'), {
      qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z', 11)],
      entityTerms: springfieldParliament,
    }),
  ],
  actions: [
    createAction('tutorial-create-birth-date', 'P569', timeValue('+1975-03-15T00:00:00Z', 11), [
      evidence('ref-tutorial-1', page1, birthDateQuotes),
    ]),
  ],
}

// --- Interactive review steps keyed by tutorial step ---

export const tutorialReviewSteps: Partial<Record<TutorialStep, TutorialReviewStep>> = {
  [TutorialStep.BirthDateDecisions]: {
    politician: {
      id: 'tutorial-politician-birth-date',
      ...politicianBase,
      sources: [page1],
      statements: [],
      actions: [
        createAction(
          'tutorial-create-mothers-birth-date',
          'P569',
          timeValue('+1952-06-08T00:00:00Z', 11),
          [
            evidence('ref-tutorial-2', page1, [
              'Following in the footsteps of her mother Mary Doe (born June 8, 1952), she pursued a career in public service.',
            ]),
          ],
        ),
        createAction('tutorial-create-birth-date', 'P569', timeValue('+1975-03-15T00:00:00Z', 11), [
          evidence('ref-tutorial-3', page1, birthDateQuotes),
        ]),
      ],
    },
    expectedDecisions: {
      'tutorial-create-mothers-birth-date': false, // Discard - June 8, 1952 is the mother's birth date
      'tutorial-create-birth-date': true, // Accept - March 15, 1975 is correct
    },
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

  [TutorialStep.MultipleSourcesDecisions]: {
    politician: {
      id: 'tutorial-politician-multiple-sources',
      ...politicianBase,
      sources: [page1, page2],
      statements: [],
      actions: [
        createAction(
          'tutorial-create-springfield-member',
          'P39',
          entityValue('Q1343573'),
          [evidence('ref-tutorial-4', page1, springfieldMemberQuotes)],
          {
            qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z', 11)],
            entityTerms: springfieldParliament,
          },
        ),
        createAction(
          'tutorial-create-minister',
          'P39',
          entityValue('Q4018482'),
          [
            evidence('ref-tutorial-5', page2, [
              'She was appointed Minister of Education in June 2022.',
              'Current Minister of Education since 2022',
            ]),
          ],
          {
            qualifiers: [startTimeQualifier('+2022-06-00T00:00:00Z', 10)],
            entityTerms: ministerOfEducation,
          },
        ),
      ],
    },
    expectedDecisions: {
      'tutorial-create-springfield-member': true,
      'tutorial-create-minister': true,
    },
    backStep: TutorialStep.MultipleSources,
    success: {
      title: 'Great Job!',
      message:
        'You correctly verified both positions from their respective source documents. Being able to work with multiple sources is an important skill!',
    },
    error: {
      title: "Let's Try Again",
      message:
        'Make sure to check each position against its source document. Click "View" to switch between sources and verify each proposal.',
      hint: "Hint: Read each source carefully — does the proposed statement match what's written?",
    },
  },

  [TutorialStep.SpecificOverGenericDecisions]: {
    politician: {
      id: 'tutorial-politician-specific-over-generic',
      ...politicianBase,
      sources: [page1],
      statements: [
        statement('Q955672$springfield-member', 'P39', entityValue('Q1343573'), {
          qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z', 11)],
          entityTerms: springfieldParliament,
        }),
      ],
      actions: [
        createAction(
          'tutorial-create-generic-member',
          'P39',
          entityValue('Q486839'),
          [evidence('ref-tutorial-6', page1, springfieldMemberQuotes)],
          {
            qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z', 11)],
            entityTerms: memberOfParliament,
          },
        ),
      ],
    },
    expectedDecisions: {
      'tutorial-create-generic-member': false, // Discard - generic when specific exists
    },
    backStep: TutorialStep.SpecificOverGeneric,
    success: {
      title: 'Perfect!',
      message:
        'You correctly discarded the generic "Member of Parliament" because the more specific "Member of Springfield Parliament" already exists. Quality over quantity!',
    },
    error: {
      title: 'Almost There',
      message:
        "Remember: when we already have specific data, we don't need a generic version. Look at what data already exists before accepting new proposals.",
      hint: 'Hint: "Member of Springfield Parliament" is more specific than "Member of Parliament".',
    },
  },

  [TutorialStep.RefiningValuesDecisions]: {
    politician: {
      id: 'tutorial-politician-refining-values',
      ...politicianBase,
      sources: [page1],
      statements: [statement('Q955672$birth-date', 'P569', timeValue('+1975-00-00T00:00:00Z', 9))],
      actions: [
        editAction(
          'tutorial-edit-birth-date-precision',
          'Q955672$birth-date',
          [
            {
              op: 'test',
              path: '/value',
              value: timeValue('+1975-00-00T00:00:00Z', 9),
            },
            { op: 'replace', path: '/value', value: timeValue('+1975-03-15T00:00:00Z', 11) },
          ],
          [evidence('ref-tutorial-7', page1, birthDateQuotes)],
        ),
      ],
    },
    expectedDecisions: {
      'tutorial-edit-birth-date-precision': true, // Accept - the source pins down the exact day
    },
    backStep: TutorialStep.RefiningValues,
    success: {
      title: 'Nice Work!',
      message:
        'The source states the full date, so replacing the bare year with March 15, 1975 makes Wikidata more precise. That is exactly what a good refinement does.',
    },
    error: {
      title: 'Not Quite Right',
      message:
        'Check the evidence under the proposal — the parliament profile states the exact day Jane Doe was born.',
      hint: 'Hint: A more precise value that the source supports is worth keeping.',
    },
  },

  [TutorialStep.CompletingTimeframesDecisions]: {
    politician: {
      id: 'tutorial-politician-completing-timeframes',
      ...politicianBase,
      sources: [page1, page2],
      statements: [
        statement('Q955672$springfield-member', 'P39', entityValue('Q1343573'), {
          entityTerms: springfieldParliament,
        }),
        statement('Q955672$minister', 'P39', entityValue('Q4018482'), {
          qualifiers: [startTimeQualifier('+2022-06-00T00:00:00Z', 10)],
          entityTerms: ministerOfEducation,
        }),
      ],
      actions: [
        editAction(
          'tutorial-edit-springfield-start',
          'Q955672$springfield-member',
          [
            { op: 'test', path: '/qualifiers', value: [] },
            {
              op: 'add',
              path: '/qualifiers/-',
              value: startTimeQualifier('+2020-01-01T00:00:00Z', 11),
            },
          ],
          [evidence('ref-tutorial-8', page1, springfieldMemberQuotes)],
          { entityTerms: springfieldParliament },
        ),
        editAction(
          'tutorial-edit-minister-start',
          'Q955672$minister',
          [
            {
              op: 'test',
              path: '/qualifiers/0',
              value: startTimeQualifier('+2022-06-00T00:00:00Z', 10),
            },
            {
              op: 'replace',
              path: '/qualifiers/0',
              value: startTimeQualifier('+2015-06-00T00:00:00Z', 10),
            },
          ],
          [
            evidence('ref-tutorial-9', page2, [
              'Doe began her political career as a city councillor from 2015 to 2019.',
            ]),
          ],
          { entityTerms: ministerOfEducation },
        ),
      ],
    },
    expectedDecisions: {
      'tutorial-edit-springfield-start': true, // Accept - the source states the start date
      'tutorial-edit-minister-start': false, // Discard - the quote is about her council career
    },
    backStep: TutorialStep.CompletingTimeframes,
    success: {
      title: 'Well Done!',
      message:
        'You added the missing start date for the parliament membership and caught that the "city councillor" dates were wrongly attached to the ministry. Evidence is everything!',
    },
    error: {
      title: 'Not Quite Right',
      message:
        'One edit is backed by its source and one is not. Open each proposal and compare the proposed timeframe with its evidence.',
      hint: 'Hint: "City councillor from 2015 to 2019" is not the same job as Minister of Education.',
    },
  },

  [TutorialStep.AddingReferencesDecisions]: {
    politician: {
      id: 'tutorial-politician-adding-references',
      ...politicianBase,
      sources: [page1, page2],
      statements: [
        statement('Q955672$birthplace', 'P19', entityValue('Q6490542'), {
          entityTerms: springfieldCity,
        }),
        statement('Q955672$citizenship', 'P27', entityValue('Q999001'), {
          references: [
            {
              parts: [
                {
                  property: { id: 'P143' },
                  value: entityValue('Q328'),
                },
              ],
            },
          ],
          entityTerms: springfieldRepublic,
        }),
      ],
      actions: [
        editAction(
          'tutorial-edit-birthplace-reference',
          'Q955672$birthplace',
          [
            { op: 'test', path: '/references', value: [] },
            {
              op: 'add',
              path: '/references/-',
              value: {
                parts: [
                  {
                    property: { id: 'P854' },
                    value: entityValue('https://example.parliament.gov/members/jane-doe'),
                  },
                  { property: { id: 'P813' }, value: timeValue('+2024-01-15T00:00:00Z', 11) },
                ],
              },
            },
          ],
          [evidence('ref-tutorial-10', page1, birthDateQuotes)],
        ),
        editAction(
          'tutorial-edit-citizenship-reference',
          'Q955672$citizenship',
          [
            {
              op: 'test',
              path: '/references',
              value: [
                {
                  parts: [
                    {
                      property: { id: 'P143' },
                      value: entityValue('Q328'),
                    },
                  ],
                },
              ],
            },
            {
              op: 'add',
              path: '/references/-',
              value: {
                parts: [
                  {
                    property: { id: 'P4656' },
                    value: entityValue(
                      'https://en.wikipedia.org/w/index.php?title=Jane_Doe_(politician)&oldid=1195236721',
                    ),
                  },
                  { property: { id: 'P813' }, value: timeValue('+2024-01-15T00:00:00Z', 11) },
                ],
              },
            },
          ],
          [evidence('ref-tutorial-11', page2, ['Doe resides in Springfield with her family.'])],
        ),
      ],
    },
    expectedDecisions: {
      'tutorial-edit-birthplace-reference': true, // Accept - the source states she was born in Springfield
      'tutorial-edit-citizenship-reference': false, // Discard - residing somewhere is not citizenship evidence
    },
    backStep: TutorialStep.AddingReferences,
    success: {
      title: 'Great Choice!',
      message:
        'You accepted a reference that proves the birthplace and rejected one that does not actually back the citizenship statement. Wikidata is only as good as its sources.',
    },
    error: {
      title: "Let's Reconsider",
      message:
        'Only accept a reference when its evidence truly supports the statement. Read each quote and ask: does this prove the claim?',
      hint: 'Hint: "Doe resides in Springfield with her family" says nothing about citizenship.',
    },
  },
}
