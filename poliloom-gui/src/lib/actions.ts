import type {
  Action,
  ActionEvidence,
  ReviewSubmitPayload,
  Statement,
  StatementFact,
  SubmittedAction,
} from '@/types'
import { parseTimeValue, timeValue, type ParsedTime } from '@/lib/wikidata/dateParser'
import { compareTimes, parseTimeframe } from '@/lib/wikidata/qualifierParser'

// --- Review decision state ---

/** Explicit review decisions by proposal key. */
export type ProposalDecisions = Record<string, boolean>

/** Expand each proposal decision to the action IDs currently in the review. */
export function buildSubmission(
  actions: Action[],
  decisions: ProposalDecisions,
): ReviewSubmitPayload {
  const submitted: SubmittedAction[] = []
  const skips: string[] = []

  for (const action of actions) {
    const decision = decisions[action.group_key]
    if (decision === undefined) {
      skips.push(action.id)
      continue
    }
    submitted.push({ id: action.id, is_accepted: decision })
  }

  return { actions: submitted, skips }
}

// --- Statement grouping ---

export type SectionType = 'date' | 'P39' | 'P19' | 'P27'

/** A cached statement with its proposals, or a standalone proposal. */
export interface StatementItem {
  statement: Statement | null
  /** Proposals for this item, grouped by the server-supplied group key. */
  proposals: Action[][]
}

export function statementItemKey(item: StatementItem): string {
  return item.statement ? item.statement.document.id : item.proposals[0][0].group_key
}

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
  const action = item.proposals[0]?.[0]
  if (!action) {
    throw new Error('Statement item has neither a statement nor proposals')
  }
  return action.after
}

/** Group equivalent proposals by the server-supplied group key. */
export function groupProposals(actions: Action[]): Action[][] {
  const groups = new Map<string, Action[]>()
  for (const action of actions) {
    const group = groups.get(action.group_key) ?? []
    group.push(action)
    groups.set(action.group_key, group)
  }
  return Array.from(groups.values())
}

/** Combine a proposal's evidence by source, preserving every distinct quote. */
export function proposalEvidence(actions: Action[]): ActionEvidence[] {
  const evidenceBySource = new Map<string, ActionEvidence>()
  for (const action of actions) {
    for (const evidence of action.evidence) {
      const existing = evidenceBySource.get(evidence.source.id)
      evidenceBySource.set(
        evidence.source.id,
        existing
          ? {
              ...existing,
              supporting_quotes: Array.from(
                new Set([
                  ...(existing.supporting_quotes ?? []),
                  ...(evidence.supporting_quotes ?? []),
                ]),
              ),
            }
          : evidence,
      )
    }
  }
  return Array.from(evidenceBySource.values())
}

function buildItems(statements: Statement[], actions: Action[]): StatementItem[] {
  const byDocumentId = new Map(
    statements.map((statement) => [statement.document.id, { statement, actions: [] as Action[] }]),
  )
  const standalone: Action[] = []

  for (const action of actions) {
    if (action.change !== 'add' && action.target_wikidata_statement_id === null) {
      throw new Error(`Action ${action.id} changes an existing statement but has no target`)
    }
    const item =
      action.target_wikidata_statement_id === null
        ? undefined
        : byDocumentId.get(action.target_wikidata_statement_id)
    if (item) {
      item.actions.push(action)
    } else {
      standalone.push(action)
    }
  }

  return [
    ...Array.from(byDocumentId.values(), (item) => ({
      statement: item.statement,
      proposals: groupProposals(item.actions),
    })),
    ...groupProposals(standalone).map((proposal) => ({ statement: null, proposals: [proposal] })),
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
): StatementSection[] {
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
  if (dateItems.size > 0) {
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
