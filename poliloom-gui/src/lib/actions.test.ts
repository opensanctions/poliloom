import { describe, it, expect } from 'vitest'
import {
  buildSubmission,
  effectiveDecision,
  groupActions,
  groupStatementsIntoSections,
  itemFact,
} from './actions'
import type {
  Action,
  RestReference,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  Statement,
  StatementFact,
} from '@/types'

// --- Fixtures ---

const mockSource: SourceResponse = {
  id: 'src-1',
  url: 'https://example.com',
  url_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const timeContent = (time: string, precision: number): RestValue => ({
  type: 'value',
  content: { time, precision, calendarmodel: 'http://www.wikidata.org/entity/Q1985727' },
})

const entityContent = (qid: string): RestValue => ({ type: 'value', content: qid })

const startTimeQualifier = (time: string, precision = 11): RestSnak => ({
  property: { id: 'P580' },
  value: timeContent(time, precision),
})

function fact(propertyId: string, value: RestValue, qualifiers: RestSnak[] = []): StatementFact {
  return { property: { id: propertyId }, value, qualifiers }
}

function statement(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    documentId?: string
    qualifiers?: RestSnak[]
    references?: RestReference[]
  } = {},
): Statement {
  const document: RestStatement = {
    id: options.documentId ?? id,
    rank: 'normal',
    property: { id: propertyId },
    value,
    qualifiers: options.qualifiers ?? [],
    references: options.references ?? [],
  }
  return { id, document, entity_terms: null }
}

function action(
  id: string,
  options: {
    change?: Action['change']
    target?: string | null
    before?: StatementFact | null
    after?: StatementFact
    groupKey?: string
    referencesToAdd?: RestReference[]
    isAccepted?: boolean | null
  } = {},
): Action {
  return {
    id,
    target_wikidata_statement_id: options.target ?? null,
    before: options.before ?? null,
    after: options.after ?? fact('P569', timeContent('+2000-01-01T00:00:00Z', 11)),
    references_to_add: options.referencesToAdd ?? [],
    applied_wikidata_statement_id: null,
    group_key: options.groupKey ?? id,
    change: options.change ?? 'add',
    entity_terms: null,
    evidence: [{ id: `ev-${id}`, source: mockSource, supporting_quotes: null }],
    is_accepted: options.isAccepted ?? null,
    applied_at: null,
    error: null,
  }
}

function addAction(
  id: string,
  propertyId: string,
  value: RestValue,
  qualifiers: RestSnak[] = [],
  groupKey = id,
): Action {
  return action(id, {
    change: 'add',
    after: fact(propertyId, value, qualifiers),
    groupKey,
  })
}

function editAction(
  id: string,
  target: string,
  before: StatementFact,
  after: StatementFact,
  groupKey = id,
): Action {
  return action(id, { change: 'refine', target, before, after, groupKey })
}

// --- Decision state ---

describe('effectiveDecision', () => {
  it('falls back to the served decision when there is no local override', () => {
    expect(effectiveDecision(action('a1', { isAccepted: true }), {})).toBe(true)
    expect(effectiveDecision(action('a1', { isAccepted: false }), {})).toBe(false)
    expect(effectiveDecision(action('a1'), {})).toBeNull()
  })

  it('uses the local override when present, including null', () => {
    const subject = action('a1', { isAccepted: true })
    expect(effectiveDecision(subject, { a1: true })).toBe(true)
    expect(effectiveDecision(subject, { a1: null })).toBeNull()
  })

  it('keeps equivalent proposals independently decidable', () => {
    const first = addAction('a1', 'P19', entityContent('Q300'), [], 'same-proposal')
    const second = addAction('a2', 'P19', entityContent('Q300'), [], 'same-proposal')

    expect(effectiveDecision(first, { a1: true })).toBe(true)
    expect(effectiveDecision(second, { a1: true })).toBeNull()
  })
})

describe('buildSubmission', () => {
  it('emits decided actions as id/decision pairs', () => {
    const created = action('a1')
    const edited = action('a2', {
      change: 'refine',
      target: 's1',
      before: fact('P569', entityContent('Q1')),
    })

    const payload = buildSubmission([created, edited], { a1: true, a2: false })

    expect(payload).toEqual({
      actions: [
        { id: 'a1', is_accepted: true },
        { id: 'a2', is_accepted: false },
      ],
      skips: [],
    })
  })

  it('emits served decisions when there is no local override', () => {
    const accepted = action('a1', { isAccepted: true })
    const discarded = action('a2', { isAccepted: false })

    expect(buildSubmission([accepted, discarded], {})).toEqual({
      actions: [
        { id: 'a1', is_accepted: true },
        { id: 'a2', is_accepted: false },
      ],
      skips: [],
    })
  })

  it('never emits null decisions: actions reset to undecided are skipped', () => {
    expect(buildSubmission([action('a1', { isAccepted: true })], { a1: null })).toEqual({
      actions: [],
      skips: ['a1'],
    })
  })

  it('skips only still-undecided actions', () => {
    const actions = [action('a1'), action('a2')]

    const payload = buildSubmission(actions, { a1: true })

    expect(payload.actions.map((entry) => entry.id)).toEqual(['a1'])
    expect(payload.skips).toEqual(['a2'])
  })

  it('ignores a decision for a row no longer present', () => {
    expect(buildSubmission([], { a1: true })).toEqual({ actions: [], skips: [] })
  })
})

// --- Action grouping ---

describe('groupActions', () => {
  it('groups actions by the supplied group key and keeps ids separate', () => {
    const first = addAction('a1', 'P19', entityContent('Q300'), [], 'g1')
    const second = addAction('a2', 'P19', entityContent('Q300'), [], 'g1')
    const third = addAction('a3', 'P19', entityContent('Q300'), [], 'g2')

    expect(groupActions([first, second, third])).toEqual([[first, second], [third]])
  })

  it('does not infer groups from equal data', () => {
    const first = addAction('a1', 'P19', entityContent('Q300'), [], 'g1')
    const second = addAction('a2', 'P19', entityContent('Q300'), [], 'g2')

    expect(groupActions([first, second])).toEqual([[first], [second]])
  })
})

// --- Statement grouping ---

const birthDate = statement('row-1', 'P569', timeContent('+1990-05-15T00:00:00Z', 11), {
  documentId: 'Q1$birth',
})
const deathDate = statement('row-2', 'P570', timeContent('+2020-01-01T00:00:00Z', 11))
const governor2018 = statement('row-3', 'P39', entityContent('Q200'), {
  qualifiers: [startTimeQualifier('+2018-01-01T00:00:00Z')],
})
const governor2022 = statement('row-3b', 'P39', entityContent('Q200'), {
  qualifiers: [startTimeQualifier('+2022-01-01T00:00:00Z')],
})
const mayor2020 = statement('row-4', 'P39', entityContent('Q100'), {
  qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z')],
})
const birthplace = statement('row-5', 'P19', entityContent('Q300'))
const citizenship = statement('row-6', 'P27', entityContent('Q400'))

describe('groupStatementsIntoSections', () => {
  it('returns sections with correct titles', () => {
    const sections = groupStatementsIntoSections(
      [birthDate, governor2018, birthplace, citizenship],
      [],
    )

    expect(sections.map((s) => s.title)).toEqual([
      'Dates',
      'Political Positions',
      'Birthplaces',
      'Citizenships',
    ])
  })

  it('groups birth and death dates under the Dates section keyed by property', () => {
    const sections = groupStatementsIntoSections([birthDate, deathDate], [])

    expect(sections).toHaveLength(1)
    expect(sections[0].sectionType).toBe('date')
    expect(sections[0].groups.map((g) => g.key)).toEqual(['P569', 'P570'])
  })

  it('sorts dates by precision then value', () => {
    const vague = statement('s7', 'P569', timeContent('+1990-00-00T00:00:00Z', 9))
    const sections = groupStatementsIntoSections([vague, birthDate], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['row-1', 's7'])
  })

  it('sorts statements without a date value last', () => {
    const unknown = statement('s8', 'P569', { type: 'somevalue' })
    const sections = groupStatementsIntoSections([unknown, birthDate], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['row-1', 's8'])
  })

  it('groups positions by entity QID', () => {
    const sections = groupStatementsIntoSections([governor2018, governor2022, mayor2020], [])

    expect(sections).toHaveLength(1)
    expect(sections[0].groups.map((g) => g.key)).toEqual(['Q200', 'Q100'])
  })

  it('sorts statements within a group by start date', () => {
    const sections = groupStatementsIntoSections([governor2022, governor2018], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['row-3', 'row-3b'])
  })

  it('sorts groups by their earliest start date', () => {
    const sections = groupStatementsIntoSections([mayor2020, governor2018], [])

    expect(sections[0].groups.map((g) => g.key)).toEqual(['Q200', 'Q100'])
  })

  it('sorts statements without a timeframe last', () => {
    const timeless = statement('s9', 'P39', entityContent('Q200'))
    const sections = groupStatementsIntoSections([timeless, governor2018], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['row-3', 's9'])
  })

  it('attaches edit actions to the cached statement matched by document id', () => {
    const valueRefinement = editAction(
      'a1',
      'Q1$birth',
      fact('P569', timeContent('+1990-05-15T00:00:00Z', 11)),
      fact('P569', timeContent('+1990-05-16T00:00:00Z', 11)),
    )
    const sections = groupStatementsIntoSections([birthDate, mayor2020], [valueRefinement])

    const dates = sections[0].groups[0].items[0]
    expect(dates.statement).toBe(birthDate)
    expect(dates.actions).toEqual([valueRefinement])
  })

  it('places add actions as standalone items in their section', () => {
    const created = addAction('a1', 'P39', entityContent('Q500'), [
      startTimeQualifier('+2024-01-01T00:00:00Z'),
    ])
    const sections = groupStatementsIntoSections([governor2018], [created])

    expect(sections[0].groups.map((g) => g.key)).toEqual(['Q200', 'Q500'])
    const standalone = sections[0].groups.find((g) => g.key === 'Q500')!
    expect(standalone.items).toEqual([{ statement: null, actions: [created] }])
  })

  it('groups actions by their supplied group key without merging ids', () => {
    const first = addAction('a1', 'P39', entityContent('Q500'), [], 'g1')
    const second = addAction('a2', 'P39', entityContent('Q500'), [], 'g1')
    const differentGroup = addAction('a3', 'P39', entityContent('Q500'), [], 'g2')

    const sections = groupStatementsIntoSections([], [first, second, differentGroup])

    expect(sections[0].groups[0].items).toEqual([
      { statement: null, actions: [first, second] },
      { statement: null, actions: [differentGroup] },
    ])
  })

  it('sorts create actions together with statements by timeframe', () => {
    const created = addAction('a1', 'P39', entityContent('Q200'), [
      startTimeQualifier('+2000-01-01T00:00:00Z'),
    ])
    const sections = groupStatementsIntoSections([governor2018], [created])

    expect(sections[0].groups[0].items.map((i) => i.statement?.id ?? i.actions[0].id)).toEqual([
      'a1',
      'row-3',
    ])
  })

  it('keeps a stable target when its cached statement is missing', () => {
    const orphan = editAction(
      'a1',
      'Q1$gone',
      fact('P569', timeContent('+1990-05-15T00:00:00Z', 11)),
      fact('P569', timeContent('+1990-05-16T00:00:00Z', 11)),
    )
    const sections = groupStatementsIntoSections([], [orphan])

    expect(orphan.target_wikidata_statement_id).toBe('Q1$gone')
    expect(sections[0].groups[0].items).toEqual([{ statement: null, actions: [orphan] }])
    expect(itemFact(sections[0].groups[0].items[0])).toEqual(orphan.after)
  })

  it('throws for statements with unexpected properties', () => {
    const occupation = statement('s1', 'P106', entityContent('Q82955'))

    expect(() => groupStatementsIntoSections([occupation], [])).toThrow(/P106/)
  })

  it('omits empty sections by default', () => {
    const sections = groupStatementsIntoSections([birthDate], [])

    expect(sections.map((s) => s.title)).toEqual(['Dates'])
  })

  it('includes empty sections when showEmptySections is true', () => {
    const sections = groupStatementsIntoSections([birthDate], [], { showEmptySections: true })

    expect(sections.map((s) => s.title)).toEqual([
      'Dates',
      'Political Positions',
      'Birthplaces',
      'Citizenships',
    ])
    expect(sections[1].groups).toHaveLength(0)
  })

  it('returns an empty array for no statements and no actions', () => {
    expect(groupStatementsIntoSections([], [])).toEqual([])
  })

  it('sorts a reference-only proposal by its cached statement context', () => {
    const reference = action('a1', {
      change: 'reference',
      target: 'Q1$birth',
      before: fact('P569', timeContent('+1990-05-15T00:00:00Z', 11)),
      after: fact('P569', timeContent('+1990-05-15T00:00:00Z', 11)),
      referencesToAdd: [
        { parts: [{ property: { id: 'P854' }, value: entityContent('https://x') }] },
      ],
    })
    const sections = groupStatementsIntoSections([birthDate], [reference])

    expect(sections[0].groups[0].items[0].statement).toBe(birthDate)
    expect(itemFact(sections[0].groups[0].items[0]).value).toEqual(birthDate.document.value)
  })
})
