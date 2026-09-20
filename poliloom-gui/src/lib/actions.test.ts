import { describe, it, expect } from 'vitest'
import {
  applyDecision,
  computeSubmitPayload,
  describePatch,
  effectiveDecision,
  groupStatementsIntoSections,
} from './actions'
import type {
  Action,
  JsonPatchOperation,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  Statement,
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

const endTimeQualifier = (time: string, precision = 11): RestSnak => ({
  property: { id: 'P582' },
  value: timeContent(time, precision),
})

function statement(
  id: string,
  propertyId: string,
  value: RestValue,
  qualifiers: RestSnak[] = [],
): Statement {
  const document: RestStatement = {
    id,
    rank: 'normal',
    property: { id: propertyId },
    value,
    qualifiers,
    references: [],
  }
  return { id, document, entity_terms: null }
}

function pendingAction(id: string, isAccepted: boolean | null = null): Action {
  return {
    id,
    kind: 'CREATE_STATEMENT',
    statement_id: null,
    payload: {
      statement: {
        rank: 'normal',
        property: { id: 'P569' },
        value: timeContent('+2000-01-01T00:00:00Z', 11),
        qualifiers: [],
        references: [],
      },
    },
    entity_terms: null,
    evidence: [{ id: 'ev-1', source: mockSource, supporting_quotes: null }],
    is_accepted: isAccepted,
    applied_at: null,
    error: null,
  }
}

function createAction(
  id: string,
  propertyId: string,
  value: RestValue,
  qualifiers: RestSnak[] = [],
): Action {
  return {
    ...pendingAction(id),
    payload: {
      statement: {
        rank: 'normal',
        property: { id: propertyId },
        value,
        qualifiers,
        references: [],
      },
    },
  }
}

function editAction(id: string, statementId: string, patch: JsonPatchOperation[]): Action {
  return {
    ...pendingAction(id),
    kind: 'EDIT_STATEMENT',
    statement_id: statementId,
    payload: { patch },
  }
}

// --- Decision state ---

describe('effectiveDecision', () => {
  it('falls back to the served decision when there is no local override', () => {
    expect(effectiveDecision(pendingAction('a1', true), {})).toBe(true)
    expect(effectiveDecision(pendingAction('a1', false), {})).toBe(false)
    expect(effectiveDecision(pendingAction('a1', null), {})).toBeNull()
  })

  it('uses the local override when present, including null', () => {
    expect(effectiveDecision(pendingAction('a1', null), { a1: true })).toBe(true)
    expect(effectiveDecision(pendingAction('a1', true), { a1: null })).toBeNull()
  })

  it('ignores overrides for other actions', () => {
    expect(effectiveDecision(pendingAction('a1', null), { a2: true })).toBeNull()
  })
})

describe('applyDecision', () => {
  it('accepts an undecided action', () => {
    expect(applyDecision(pendingAction('a1'), {}, true)).toEqual({ a1: true })
  })

  it('discards an undecided action', () => {
    expect(applyDecision(pendingAction('a1'), {}, false)).toEqual({ a1: false })
  })

  it('returns to null when clicking the active choice', () => {
    expect(applyDecision(pendingAction('a1'), { a1: true }, true)).toEqual({ a1: null })
    expect(applyDecision(pendingAction('a1'), { a1: false }, false)).toEqual({ a1: null })
  })

  it('returns to null when clicking the choice the backend already served', () => {
    expect(applyDecision(pendingAction('a1', true), {}, true)).toEqual({ a1: null })
  })

  it('switches to the other choice', () => {
    expect(applyDecision(pendingAction('a1'), { a1: true }, false)).toEqual({ a1: false })
  })

  it('preserves other decisions', () => {
    expect(applyDecision(pendingAction('a1'), { a2: true }, true)).toEqual({
      a2: true,
      a1: true,
    })
  })

  it('does not mutate the input decisions', () => {
    const decisions = { a1: true }
    applyDecision(pendingAction('a1'), decisions, false)
    expect(decisions).toEqual({ a1: true })
  })
})

describe('computeSubmitPayload', () => {
  it('includes only decisions that differ from the served state', () => {
    const actions = [
      pendingAction('a1', null),
      pendingAction('a2', null),
      pendingAction('a3', true),
    ]

    const payload = computeSubmitPayload(actions, { a1: true, a2: null })

    expect(payload.decisions).toEqual([{ id: 'a1', is_accepted: true }])
  })

  it('includes a reset to undecided when the backend served a decision', () => {
    const actions = [pendingAction('a1', true)]

    const payload = computeSubmitPayload(actions, { a1: null })

    expect(payload.decisions).toEqual([{ id: 'a1', is_accepted: null }])
  })

  it('skips still-undecided actions', () => {
    const actions = [pendingAction('a1', null), pendingAction('a2', null)]

    const payload = computeSubmitPayload(actions, { a1: true })

    expect(payload.skips).toEqual(['a2'])
  })

  it('does not skip decided actions', () => {
    const actions = [pendingAction('a1', true), pendingAction('a2', null)]

    const payload = computeSubmitPayload(actions, { a2: false })

    expect(payload.skips).toEqual([])
  })

  it('skips actions toggled back to undecided', () => {
    const actions = [pendingAction('a1', true)]

    const payload = computeSubmitPayload(actions, { a1: null })

    expect(payload.skips).toEqual(['a1'])
  })

  it('returns an empty payload when nothing changed', () => {
    const actions = [pendingAction('a1', true)]

    expect(computeSubmitPayload(actions, {})).toEqual({ decisions: [], skips: [] })
  })

  it('returns an empty payload for no actions', () => {
    expect(computeSubmitPayload([], { a1: true })).toEqual({ decisions: [], skips: [] })
  })
})

// --- Statement grouping ---

const birthDate = statement('s1', 'P569', timeContent('+1990-05-15T00:00:00Z', 11))
const deathDate = statement('s2', 'P570', timeContent('+2020-01-01T00:00:00Z', 11))
const governor2018 = statement('s3', 'P39', entityContent('Q200'), [
  startTimeQualifier('+2018-01-01T00:00:00Z'),
])
const governor2022 = statement('s3b', 'P39', entityContent('Q200'), [
  startTimeQualifier('+2022-01-01T00:00:00Z'),
])
const mayor2020 = statement('s4', 'P39', entityContent('Q100'), [
  startTimeQualifier('+2020-01-01T00:00:00Z'),
])
const birthplace = statement('s5', 'P19', entityContent('Q300'))
const citizenship = statement('s6', 'P27', entityContent('Q400'))

describe('groupStatementsIntoSections', () => {
  it('returns sections with correct titles', () => {
    const sections = groupStatementsIntoSections(
      [birthDate, governor2018, birthplace, citizenship],
      [],
    )

    expect(sections.map((s) => s.title)).toEqual([
      'Properties',
      'Political Positions',
      'Birthplaces',
      'Citizenships',
    ])
  })

  it('groups birth and death dates under the Properties section keyed by property', () => {
    const sections = groupStatementsIntoSections([birthDate, deathDate], [])

    expect(sections).toHaveLength(1)
    expect(sections[0].sectionType).toBe('date')
    expect(sections[0].groups.map((g) => g.key)).toEqual(['P569', 'P570'])
  })

  it('sorts dates by precision then value', () => {
    const vague = statement('s7', 'P569', timeContent('+1990-00-00T00:00:00Z', 9))
    const sections = groupStatementsIntoSections([vague, birthDate], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['s1', 's7'])
  })

  it('sorts statements without a date value last', () => {
    const unknown = statement('s8', 'P569', { type: 'somevalue' })
    const sections = groupStatementsIntoSections([unknown, birthDate], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['s1', 's8'])
  })

  it('groups positions by entity QID', () => {
    const sections = groupStatementsIntoSections([governor2018, governor2022, mayor2020], [])

    expect(sections).toHaveLength(1)
    expect(sections[0].groups.map((g) => g.key)).toEqual(['Q200', 'Q100'])
  })

  it('sorts statements within a group by start date', () => {
    const sections = groupStatementsIntoSections([governor2022, governor2018], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['s3', 's3b'])
  })

  it('sorts groups by their earliest start date', () => {
    const sections = groupStatementsIntoSections([mayor2020, governor2018], [])

    expect(sections[0].groups.map((g) => g.key)).toEqual(['Q200', 'Q100'])
  })

  it('sorts statements without a timeframe last', () => {
    const timeless = statement('s9', 'P39', entityContent('Q200'))
    const sections = groupStatementsIntoSections([timeless, governor2018], [])

    expect(sections[0].groups[0].items.map((i) => i.statement!.id)).toEqual(['s3', 's9'])
  })

  it('attaches edit actions to their target statement', () => {
    const valueRefinement = editAction('a1', 's3', [
      { op: 'test', path: '/value', value: entityContent('Q200') },
      { op: 'replace', path: '/value', value: entityContent('Q201') },
    ])
    const sections = groupStatementsIntoSections([governor2018, mayor2020], [valueRefinement])

    const governor = sections[0].groups.find((g) => g.key === 'Q200')!
    expect(governor.items).toHaveLength(1)
    expect(governor.items[0]).toEqual({
      statement: governor2018,
      createAction: null,
      editActions: [valueRefinement],
    })
  })

  it('places create actions as standalone items in their section', () => {
    const created = createAction('a1', 'P39', entityContent('Q500'), [
      startTimeQualifier('+2024-01-01T00:00:00Z'),
    ])
    const sections = groupStatementsIntoSections([governor2018], [created])

    expect(sections[0].groups.map((g) => g.key)).toEqual(['Q200', 'Q500'])
    const standalone = sections[0].groups.find((g) => g.key === 'Q500')!
    expect(standalone.items).toEqual([{ statement: null, createAction: created, editActions: [] }])
  })

  it('sorts create actions together with statements by timeframe', () => {
    const created = createAction('a1', 'P39', entityContent('Q200'), [
      startTimeQualifier('+2000-01-01T00:00:00Z'),
    ])
    const sections = groupStatementsIntoSections([governor2018], [created])

    expect(sections[0].groups[0].items.map((i) => i.statement?.id ?? i.createAction!.id)).toEqual([
      'a1',
      's3',
    ])
  })

  it('throws when an edit action targets an unknown statement', () => {
    const orphan = editAction('a1', 'missing', [
      { op: 'add', path: '/references/-', value: { parts: [] } },
    ])

    expect(() => groupStatementsIntoSections([], [orphan])).toThrow(/unknown statement/)
  })

  it('throws for statements with unexpected properties', () => {
    const occupation = statement('s1', 'P106', entityContent('Q82955'))

    expect(() => groupStatementsIntoSections([occupation], [])).toThrow(/P106/)
  })

  it('omits empty sections by default', () => {
    const sections = groupStatementsIntoSections([birthDate], [])

    expect(sections.map((s) => s.title)).toEqual(['Properties'])
  })

  it('includes empty sections when showEmptySections is true', () => {
    const sections = groupStatementsIntoSections([birthDate], [], { showEmptySections: true })

    expect(sections.map((s) => s.title)).toEqual([
      'Properties',
      'Political Positions',
      'Birthplaces',
      'Citizenships',
    ])
    expect(sections[1].groups).toHaveLength(0)
  })

  it('returns an empty array for no statements and no actions', () => {
    expect(groupStatementsIntoSections([], [])).toEqual([])
  })
})

// --- Edit patch classification ---

describe('describePatch', () => {
  it('classifies a value refinement with old and new value', () => {
    const oldValue = timeContent('+1990-00-00T00:00:00Z', 9)
    const newValue = timeContent('+1990-05-15T00:00:00Z', 11)

    expect(
      describePatch([
        { op: 'test', path: '/value', value: oldValue },
        { op: 'replace', path: '/value', value: newValue },
      ]),
    ).toEqual({ kind: 'value-refinement', oldValue, newValue })
  })

  it('classifies a qualifier refinement with old and new qualifier', () => {
    const oldQualifier = startTimeQualifier('+2000-00-00T00:00:00Z', 9)
    const newQualifier = startTimeQualifier('+2000-06-01T00:00:00Z', 11)

    expect(
      describePatch([
        { op: 'test', path: '/qualifiers/0', value: oldQualifier },
        { op: 'replace', path: '/qualifiers/0', value: newQualifier },
      ]),
    ).toEqual({ kind: 'qualifier-refinement', oldQualifier, newQualifier })
  })

  it('classifies a qualifier append', () => {
    const qualifier = endTimeQualifier('+2024-01-01T00:00:00Z')

    expect(
      describePatch([
        { op: 'test', path: '/qualifiers', value: [] },
        { op: 'add', path: '/qualifiers/-', value: qualifier },
      ]),
    ).toEqual({ kind: 'qualifier-append', qualifier })
  })

  it('classifies a reference append', () => {
    const reference = {
      parts: [{ property: { id: 'P248' }, value: entityContent('Q123') }],
    }

    expect(
      describePatch([
        { op: 'test', path: '/references', value: [] },
        { op: 'add', path: '/references/-', value: reference },
      ]),
    ).toEqual({ kind: 'reference-append', reference })
  })

  it('throws for unsupported mutation paths', () => {
    expect(() => describePatch([{ op: 'replace', path: '/rank', value: 'deprecated' }])).toThrow(
      /Unsupported patch/,
    )
    expect(() =>
      describePatch([
        { op: 'test', path: '/qualifiers', value: [] },
        { op: 'add', path: '/qualifiers/0', value: {} },
      ]),
    ).toThrow(/Unsupported patch/)
  })

  it('throws for a patch without a mutation operation', () => {
    expect(() => describePatch([{ op: 'test', path: '/value', value: null }])).toThrow(
      /no mutation/,
    )
  })

  it('throws when a refinement has no matching test operation', () => {
    expect(() =>
      describePatch([
        { op: 'replace', path: '/value', value: timeContent('+2000-01-01T00:00:00Z', 11) },
      ]),
    ).toThrow(/missing a test operation/)
  })
})
