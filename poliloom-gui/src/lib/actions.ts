import type {
  Action,
  CreateStatementPayload,
  JsonPatchOperation,
  RestSnak,
  RestStatement,
  RestValue,
  Statement,
} from '@/types'
import { parseTimeValue, timeValue, type ParsedTime } from '@/lib/wikidata/dateParser'
import { compareTimes, parseTimeframe } from '@/lib/wikidata/qualifierParser'

// --- Review decision state ---

/** Local per-action decisions, overriding the served `is_accepted` until submitted. */
export type LocalDecisions = Record<string, boolean | null>

/** The decision a review renders for an action: the local override, or the served value. */
export function effectiveDecision(action: Action, decisions: LocalDecisions): boolean | null {
  return action.id in decisions ? decisions[action.id] : action.is_accepted
}

/**
 * Records an accept (true) or discard (false) decision. Clicking the currently
 * active choice returns the action to undecided (null).
 */
export function applyDecision(
  action: Action,
  decisions: LocalDecisions,
  isAccepted: boolean,
): LocalDecisions {
  if (effectiveDecision(action, decisions) === isAccepted) {
    return { ...decisions, [action.id]: null }
  }
  return { ...decisions, [action.id]: isAccepted }
}

export interface ReviewDecision {
  id: string
  is_accepted: boolean | null
}

export interface ReviewSubmitPayload {
  decisions: ReviewDecision[]
  skips: string[]
}

/**
 * Builds the review submission payload: decisions that differ from the served
 * state, plus skips for every still-undecided action.
 */
export function computeSubmitPayload(
  actions: Action[],
  decisions: LocalDecisions,
): ReviewSubmitPayload {
  const changed: ReviewDecision[] = []
  const skips: string[] = []

  for (const action of actions) {
    if (action.id in decisions && decisions[action.id] !== action.is_accepted) {
      changed.push({ id: action.id, is_accepted: decisions[action.id] })
    }
    if (effectiveDecision(action, decisions) === null) {
      skips.push(action.id)
    }
  }

  return { decisions: changed, skips }
}

// --- Statement grouping ---

export type SectionType = 'date' | 'P39' | 'P19' | 'P27'

/** A renderable review row: an existing statement with its edit actions, or a create action. */
export type StatementItem =
  | { statement: Statement; createAction: null; editActions: Action[] }
  | { statement: null; createAction: Action; editActions: [] }

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

function createPayload(action: Action): CreateStatementPayload {
  if (action.kind !== 'CREATE_STATEMENT') {
    throw new Error(`Expected CREATE_STATEMENT action, got ${action.kind}`)
  }
  return action.payload as CreateStatementPayload
}

function itemDocument(item: StatementItem): Omit<RestStatement, 'id'> {
  return item.statement ? item.statement.document : createPayload(item.createAction).statement
}

function buildItems(statements: Statement[], actions: Action[]): StatementItem[] {
  const items: {
    statement: Statement
    createAction: null
    editActions: Action[]
  }[] = []
  const indexByStatementId = new Map<string, number>()

  for (const statement of statements) {
    indexByStatementId.set(statement.id, items.length)
    items.push({ statement, createAction: null, editActions: [] })
  }
  const standalone: { statement: null; createAction: Action; editActions: [] }[] = []

  for (const action of actions) {
    if (action.kind === 'CREATE_STATEMENT') {
      standalone.push({ statement: null, createAction: action, editActions: [] })
    } else {
      const index =
        action.statement_id !== null ? indexByStatementId.get(action.statement_id) : undefined
      if (index === undefined) {
        throw new Error(`Edit action ${action.id} targets unknown statement ${action.statement_id}`)
      }
      items[index].editActions.push(action)
    }
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
  | { kind: 'qualifier-refinement'; oldQualifier: RestSnak; newQualifier: RestSnak }
  | { kind: 'qualifier-append'; qualifier: RestSnak }
  | { kind: 'reference-append'; reference: RestStatement['references'][number] }

function testValue(patch: JsonPatchOperation[], path: string): unknown {
  const test = patch.find((op) => op.op === 'test' && op.path === path)
  if (!test) {
    throw new Error(`Patch is missing a test operation for ${path}`)
  }
  return test.value
}

/**
 * Classifies a supported edit patch for rendering. Every edit patch built by
 * the backend pins the document with one `test` operation followed by a single
 * mutation.
 */
export function describePatch(patch: JsonPatchOperation[]): PatchDescription {
  const mutation = patch.find((op) => op.op !== 'test')
  if (!mutation) {
    throw new Error(`Patch has no mutation operation: ${JSON.stringify(patch)}`)
  }

  if (mutation.op === 'replace' && mutation.path === '/value') {
    return {
      kind: 'value-refinement',
      oldValue: testValue(patch, '/value') as RestValue,
      newValue: mutation.value as RestValue,
    }
  }
  if (mutation.op === 'replace' && /^\/qualifiers\/\d+$/.test(mutation.path)) {
    return {
      kind: 'qualifier-refinement',
      oldQualifier: testValue(patch, mutation.path) as RestSnak,
      newQualifier: mutation.value as RestSnak,
    }
  }
  if (mutation.op === 'add' && mutation.path === '/qualifiers/-') {
    return { kind: 'qualifier-append', qualifier: mutation.value as RestSnak }
  }
  if (mutation.op === 'add' && mutation.path === '/references/-') {
    return {
      kind: 'reference-append',
      reference: mutation.value as RestStatement['references'][number],
    }
  }

  throw new Error(`Unsupported patch operation ${mutation.op} ${mutation.path}`)
}
