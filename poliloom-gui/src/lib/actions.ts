import type {
  Action,
  CreateStatementPayload,
  EditStatementPayload,
  JsonPatchOperation,
  RestSnak,
  RestStatement,
  RestValue,
  ReviewSubmitPayload,
  Statement,
  SubmittedAction,
} from '@/types'
import { parseTimeValue, timeValue, type ParsedTime } from '@/lib/wikidata/dateParser'
import { compareTimes, parseTimeframe } from '@/lib/wikidata/qualifierParser'

// --- Review decision state ---

/** Local row decisions, overriding the served `is_accepted` until submitted. */
export type LocalDecisions = Record<string, boolean | null>

/** The decision a review renders for an action: the row override, or the served value. */
export function effectiveDecision(action: Action, decisions: LocalDecisions): boolean | null {
  const key = actionGroupKey(action)
  return key in decisions ? decisions[key] : action.is_accepted
}

/**
 * Builds the review submission payload: every decided action as a complete
 * submitted action, and every still-undecided action as a skip. Decisions are
 * never null on the wire — an action reset to undecided is skipped.
 */
export function buildSubmission(actions: Action[], decisions: LocalDecisions): ReviewSubmitPayload {
  const submitted: SubmittedAction[] = []
  const skips: string[] = []

  for (const action of actions) {
    const decision = effectiveDecision(action, decisions)
    if (decision === null) {
      skips.push(action.id)
      continue
    }
    submitted.push({
      id: action.id,
      kind: action.kind,
      statement_id: action.statement_id,
      payload: action.payload,
      is_accepted: decision,
    })
  }

  return { actions: submitted, skips }
}

// --- Statement grouping ---

export type SectionType = 'date' | 'P39' | 'P19' | 'P27'

/** A renderable review row: an existing statement with edit actions, or one create group. */
export type StatementItem =
  | { statement: Statement; createActions: []; editActions: Action[] }
  | { statement: null; createActions: Action[]; editActions: [] }

export interface StatementGroup {
  /** Entity QID for entity sections, property id for date sections. */
  key: string
  items: StatementItem[]
}

export interface StatementSection {
  title: string
  sectionType: SectionType
  groups: StatementGroup[]
}

export function itemDocument(item: StatementItem): Omit<RestStatement, 'id'> {
  if (item.statement) {
    return item.statement.document
  }
  const action = item.createActions[0]
  if (action.kind !== 'CREATE_STATEMENT') {
    throw new Error(`Expected CREATE_STATEMENT action, got ${action.kind}`)
  }
  return (action.payload as CreateStatementPayload).statement
}

function isReferenceAppend(op: JsonPatchOperation): boolean {
  return op.op === 'add' && op.path === '/references/-'
}

/** Equal proposed writes share a row regardless of the source references. */
export function actionGroupKey(action: Action): string {
  let data
  if (action.kind === 'CREATE_STATEMENT') {
    const { references: _references, ...statement } = (action.payload as CreateStatementPayload)
      .statement
    data = statement
  } else {
    data = (action.payload as EditStatementPayload).patch.filter((op) => !isReferenceAppend(op))
  }
  return JSON.stringify([action.kind, action.statement_id, data], (_, value: unknown) => {
    return value !== null && typeof value === 'object' && !Array.isArray(value)
      ? Object.fromEntries(
          Object.keys(value)
            .sort()
            .map((key) => [key, (value as Record<string, unknown>)[key]]),
        )
      : value
  })
}

export function groupActions(actions: Action[]): Action[][] {
  const groups = new Map<string, Action[]>()
  for (const action of actions) {
    const key = actionGroupKey(action)
    const group = groups.get(key) ?? []
    group.push(action)
    groups.set(key, group)
  }
  return Array.from(groups.values())
}

function buildItems(statements: Statement[], actions: Action[]): StatementItem[] {
  const items: {
    statement: Statement
    createActions: []
    editActions: Action[]
  }[] = []
  const indexByStatementId = new Map<string, number>()

  for (const statement of statements) {
    indexByStatementId.set(statement.id, items.length)
    items.push({ statement, createActions: [], editActions: [] })
  }
  const standalone: { statement: null; createActions: Action[]; editActions: [] }[] = []
  const creates: Action[] = []

  for (const action of actions) {
    if (action.kind === 'CREATE_STATEMENT') {
      creates.push(action)
    } else {
      const index =
        action.statement_id !== null ? indexByStatementId.get(action.statement_id) : undefined
      if (index === undefined) {
        throw new Error(`Edit action ${action.id} targets unknown statement ${action.statement_id}`)
      }
      items[index].editActions.push(action)
    }
  }

  for (const createActions of groupActions(creates)) {
    standalone.push({ statement: null, createActions, editActions: [] })
  }

  return [...items, ...standalone]
}

function compareByPrecisionThenTime(a: ParsedTime, b: ParsedTime): number {
  if (a.precision !== b.precision) {
    return b.precision - a.precision
  }
  return compareTimes(a, b)
}

function parsedTimeOf(item: StatementItem): ParsedTime | null {
  const time = timeValue(itemDocument(item).value)
  return time ? parseTimeValue(time) : null
}

function compareByStartDate(a: StatementItem, b: StatementItem): number {
  const startA = parseTimeframe(itemDocument(a).qualifiers).start
  const startB = parseTimeframe(itemDocument(b).qualifiers).start

  if (!startA && !startB) return 0
  if (!startA) return 1
  if (!startB) return -1

  return compareByPrecisionThenTime(startA, startB)
}

function compareByDate(a: StatementItem, b: StatementItem): number {
  const dateA = parsedTimeOf(a)
  const dateB = parsedTimeOf(b)

  if (!dateA && !dateB) return 0
  if (!dateA) return 1
  if (!dateB) return -1

  return compareByPrecisionThenTime(dateA, dateB)
}

function entityQidOf(item: StatementItem): string {
  const value = itemDocument(item).value
  if (value.type !== 'value' || typeof value.content !== 'string') {
    throw new Error(`Expected entity value for ${itemDocument(item).property.id}`)
  }
  return value.content
}

function getSectionTitle(propertyId: 'P39' | 'P19' | 'P27'): string {
  switch (propertyId) {
    case 'P39':
      return 'Political Positions'
    case 'P19':
      return 'Birthplaces'
    case 'P27':
      return 'Citizenships'
  }
}

export function groupStatementsIntoSections(
  statements: Statement[],
  actions: Action[],
  options?: { showEmptySections?: boolean },
): StatementSection[] {
  const showEmptySections = options?.showEmptySections ?? false
  const result: StatementSection[] = []

  // Partition into date items (per property) and entity-based items (per property)
  const dateItems = new Map<string, StatementItem[]>()
  const entityItems = new Map<string, StatementItem[]>()

  for (const item of buildItems(statements, actions)) {
    const propertyId = itemDocument(item).property.id
    if (propertyId === 'P569' || propertyId === 'P570') {
      const bucket = dateItems.get(propertyId) ?? []
      bucket.push(item)
      dateItems.set(propertyId, bucket)
    } else if (propertyId === 'P39' || propertyId === 'P19' || propertyId === 'P27') {
      const bucket = entityItems.get(propertyId) ?? []
      bucket.push(item)
      entityItems.set(propertyId, bucket)
    } else {
      throw new Error(`Unexpected property ${propertyId} in review statements`)
    }
  }

  // Date section: group by property (P569/P570), sort by precision then value
  if (dateItems.size > 0 || showEmptySections) {
    for (const bucket of dateItems.values()) {
      bucket.sort(compareByDate)
    }
    result.push({
      title: 'Dates',
      sectionType: 'date',
      groups: Array.from(dateItems.entries(), ([key, items]) => ({ key, items })),
    })
  }

  // Entity-based sections in fixed order, grouped by entity QID,
  // sorted within each group by start date and groups by earliest start date
  const orderedPropertyIds = ['P39', 'P19', 'P27'] as const

  for (const propertyId of orderedPropertyIds) {
    const sectionItems = entityItems.get(propertyId)
    if (!sectionItems) {
      if (showEmptySections) {
        result.push({ title: getSectionTitle(propertyId), sectionType: propertyId, groups: [] })
      }
      continue
    }

    const entityGroups = new Map<string, StatementItem[]>()
    for (const item of sectionItems) {
      const key = entityQidOf(item)
      const bucket = entityGroups.get(key) ?? []
      bucket.push(item)
      entityGroups.set(key, bucket)
    }

    for (const bucket of entityGroups.values()) {
      bucket.sort(compareByStartDate)
    }

    const groups = Array.from(entityGroups.entries(), ([key, items]) => ({ key, items })).sort(
      (a, b) => compareByStartDate(a.items[0], b.items[0]),
    )

    result.push({ title: getSectionTitle(propertyId), sectionType: propertyId, groups })
  }

  return result
}

// --- Edit patch classification ---

export type PatchDescription =
  | { kind: 'value-refinement'; oldValue: RestValue; newValue: RestValue }
  | {
      kind: 'qualifier-refinement'
      qualifierIndex: number
      oldQualifier: RestSnak
      newQualifier: RestSnak
    }
  | { kind: 'qualifier-append'; qualifier: RestSnak }

function testValue(patch: JsonPatchOperation[], path: string): unknown {
  const test = patch.find((op) => op.op === 'test' && op.path === path)
  if (!test) {
    throw new Error(`Patch is missing a test operation for ${path}`)
  }
  return test.value
}

/** Describe the data change, if any, in an edit proposal. */
export function describePatch(patch: JsonPatchOperation[]): PatchDescription | null {
  const mutation = patch.find((op) => op.op !== 'test' && !isReferenceAppend(op))
  if (!mutation) return null

  if (mutation.op === 'replace' && mutation.path === '/value') {
    return {
      kind: 'value-refinement',
      oldValue: testValue(patch, '/value') as RestValue,
      newValue: mutation.value as RestValue,
    }
  }
  const qualifierMatch =
    mutation.op === 'replace' ? mutation.path.match(/^\/qualifiers\/(\d+)$/) : null
  if (qualifierMatch) {
    return {
      kind: 'qualifier-refinement',
      qualifierIndex: Number(qualifierMatch[1]),
      oldQualifier: testValue(patch, mutation.path) as RestSnak,
      newQualifier: mutation.value as RestSnak,
    }
  }
  if (mutation.op === 'add' && mutation.path === '/qualifiers/-') {
    return { kind: 'qualifier-append', qualifier: mutation.value as RestSnak }
  }
  throw new Error(`Unsupported patch operation ${mutation.op} ${mutation.path}`)
}
