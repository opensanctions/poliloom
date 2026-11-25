import type {
  Action,
  ReviewSubmitPayload,
  Statement,
  StatementFact,
  SubmittedAction,
} from '@/types'
import { parseTimeValue, timeValue, type ParsedTime } from '@/lib/wikidata/dateParser'
import { compareTimes, parseTimeframe } from '@/lib/wikidata/qualifierParser'

// --- Review decision state ---

/** Local decisions by action id, overriding the served `is_accepted` until submitted. */
export type LocalDecisions = Record<string, boolean | null>

/** The decision a review renders for an action: the local override, or the served value. */
export function effectiveDecision(action: Action, decisions: LocalDecisions): boolean | null {
  return action.id in decisions ? decisions[action.id] : action.is_accepted
}

/**
 * Build the review submission payload: every decided action as an id/decision
 * pair, and every still-undecided action as a skip. Decisions are never null on
 * the wire — an action reset to undecided is skipped.
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
    submitted.push({ id: action.id, is_accepted: decision })
  }

  return { actions: submitted, skips }
}

// --- Statement grouping ---

export type SectionType = 'date' | 'P39' | 'P19' | 'P27'

/** A renderable review row: a cached statement with its edits, or a standalone proposal. */
export type StatementItem =
  { statement: Statement; actions: Action[] } | { statement: null; actions: Action[] }

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

/** The fact an item renders: cached context for statements, the proposal otherwise. */
export function itemFact(item: StatementItem): StatementFact {
  if (item.statement) {
    const { property, value, qualifiers } = item.statement.document
    return { property, value, qualifiers }
  }
  const action = item.actions[0]
  if (!action) {
    throw new Error('Statement item has neither a statement nor actions')
  }
  return action.after
}

/** Group equivalent proposals by the server-supplied group key. */
export function groupActions(actions: Action[]): Action[][] {
  const groups = new Map<string, Action[]>()
  for (const action of actions) {
    const group = groups.get(action.group_key) ?? []
    group.push(action)
    groups.set(action.group_key, group)
  }
  return Array.from(groups.values())
}

function buildItems(statements: Statement[], actions: Action[]): StatementItem[] {
  const items: { statement: Statement; actions: Action[] }[] = statements.map((statement) => ({
    statement,
    actions: [],
  }))
  const indexByDocumentId = new Map<string, number>()
  items.forEach((item, index) => indexByDocumentId.set(item.statement.document.id, index))

  const standalone: Action[] = []

  for (const action of actions) {
    if (action.change === 'add') {
      standalone.push(action)
      continue
    }
    if (action.target_wikidata_statement_id === null) {
      throw new Error(`Action ${action.id} changes an existing statement but has no target`)
    }
    const index = indexByDocumentId.get(action.target_wikidata_statement_id)
    if (index === undefined) {
      // The target remains stable even when its cached statement is gone.
      standalone.push(action)
      continue
    }
    items[index].actions.push(action)
  }

  return [
    ...items,
    ...groupActions(standalone).map((group) => ({ statement: null, actions: group })),
  ]
}

function compareByPrecisionThenTime(a: ParsedTime, b: ParsedTime): number {
  if (a.precision !== b.precision) {
    return b.precision - a.precision
  }
  return compareTimes(a, b)
}

function parsedTimeOf(item: StatementItem): ParsedTime | null {
  const time = timeValue(itemFact(item).value)
  return time ? parseTimeValue(time) : null
}

function compareByStartDate(a: StatementItem, b: StatementItem): number {
  const startA = parseTimeframe(itemFact(a).qualifiers).start
  const startB = parseTimeframe(itemFact(b).qualifiers).start

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
  const fact = itemFact(item)
  const value = fact.value
  if (value.type !== 'value' || typeof value.content !== 'string') {
    throw new Error(`Expected entity value for ${fact.property.id}`)
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
    const propertyId = itemFact(item).property.id
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
