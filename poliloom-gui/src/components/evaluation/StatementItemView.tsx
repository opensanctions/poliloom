import { ReactNode } from 'react'
import type {
  Action,
  ActionEvidence,
  EditStatementPayload,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  TermMaps,
} from '@/types'
import {
  actionGroupKey,
  describePatch,
  effectiveDecision,
  groupActions,
  itemDocument,
  type LocalDecisions,
  type PatchDescription,
  type StatementItem as StatementItemType,
} from '@/lib/actions'
import { best_label } from '@/lib/labels'
import { useLabelLanguages } from '@/contexts/LabelLanguageContext'
import { parseTimeValue, timeValue } from '@/lib/wikidata/dateParser'
import { formatTimeframe, parseTimeframe } from '@/lib/wikidata/qualifierParser'
import { Button } from '@/components/ui/Button'
import { StatementSource } from './StatementSource'

// --- Value display ---

function valueDisplay(value: RestValue, terms: TermMaps | null, labelLanguages: string[]): string {
  const time = timeValue(value)
  if (time) return parseTimeValue(time).display
  if (value.type === 'value') {
    if (typeof value.content === 'string' && value.content.startsWith('Q')) {
      return best_label(terms, labelLanguages, value.content)
    }
    return String(value.content)
  }
  return value.type === 'somevalue' ? 'unknown' : 'no value'
}

function InlineDiff({ before, after }: { before: string; after: string }) {
  return (
    <span className="block text-foreground-secondary">
      <span>{before}</span> <span aria-hidden="true">→</span>{' '}
      <span className="font-medium text-success-foreground">{after}</span>
    </span>
  )
}

function changedQualifiers(
  qualifiers: RestSnak[],
  description: Extract<PatchDescription, { kind: 'qualifier-refinement' | 'qualifier-append' }>,
): RestSnak[] {
  if (description.kind === 'qualifier-append') {
    return [...qualifiers, description.qualifier]
  }

  const { qualifierIndex, newQualifier } = description
  if (qualifiers[qualifierIndex]?.property.id !== newQualifier.property.id) {
    throw new Error(`Statement has no ${newQualifier.property.id} qualifier at ${qualifierIndex}`)
  }
  return qualifiers.map((qualifier, index) => (index === qualifierIndex ? newQualifier : qualifier))
}

function PatchDescriptionView({
  description,
  document,
  statementTerms,
  actionTerms,
}: {
  description: PatchDescription
  document: Pick<RestStatement, 'qualifiers'>
  statementTerms: TermMaps | null
  actionTerms: TermMaps | null
}) {
  const labelLanguages = useLabelLanguages()

  switch (description.kind) {
    case 'value-refinement':
      return (
        <InlineDiff
          before={valueDisplay(description.oldValue, statementTerms, labelLanguages)}
          after={valueDisplay(description.newValue, actionTerms, labelLanguages)}
        />
      )
    case 'qualifier-refinement':
    case 'qualifier-append': {
      const before = formatTimeframe(parseTimeframe(document.qualifiers))
      const after = formatTimeframe(
        parseTimeframe(changedQualifiers(document.qualifiers, description)),
      )
      return <InlineDiff before={before} after={after} />
    }
  }
}

// --- Decision controls ---

function DecisionButtons({
  decision,
  isSourceVisible,
  onDecision,
}: {
  decision: boolean | null
  isSourceVisible: boolean
  onDecision: (isAccepted: boolean) => void
}) {
  if (!isSourceVisible) {
    if (decision === null) {
      return <span className="text-sm text-foreground-muted">View source to decide</span>
    }
    return (
      <span
        className={`text-sm font-medium ${decision ? 'text-success-foreground' : 'text-danger-foreground'}`}
      >
        {decision ? '✓ Accepted' : '× Discarded'}
      </span>
    )
  }

  return (
    <div className="flex gap-2">
      <Button
        size="small"
        variant="success"
        active={decision === true}
        onClick={() => onDecision(true)}
        title="Mark this proposal as correct and submit it to Wikidata"
      >
        ✓ Accept
      </Button>
      <Button
        size="small"
        variant="danger"
        active={decision === false}
        onClick={() => onDecision(false)}
        title="Mark this proposal as incorrect"
      >
        × Discard
      </Button>
    </div>
  )
}

// --- Action rows ---

interface ActionRowProps {
  actions: Action[]
  document: Pick<RestStatement, 'qualifiers'>
  statementTerms: TermMaps | null
  decisions: LocalDecisions
  onDecision: (action: Action, isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover: () => void
  activeSourceId?: string | null
}

function ActionRow({
  actions,
  document,
  statementTerms,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
}: ActionRowProps) {
  const action = actions[0]
  const decision = effectiveDecision(action, decisions)
  const evidenceBySource = new Map<string, ActionEvidence>()
  for (const evidence of actions.flatMap((groupedAction) => groupedAction.evidence)) {
    const existing = evidenceBySource.get(evidence.source.id)
    if (existing) {
      existing.supporting_quotes = Array.from(
        new Set([...(existing.supporting_quotes ?? []), ...(evidence.supporting_quotes ?? [])]),
      )
    } else {
      evidenceBySource.set(evidence.source.id, { ...evidence })
    }
  }
  const evidence = Array.from(evidenceBySource.values())
  const isSourceVisible =
    evidence.length === 0 || evidence.some((e) => e.source.id === activeSourceId)
  const description =
    action.kind === 'EDIT_STATEMENT'
      ? describePatch((action.payload as EditStatementPayload).patch)
      : null
  const referenceOnly = action.kind === 'EDIT_STATEMENT' && description === null

  return (
    <div className="space-y-3">
      {description && (
        <PatchDescriptionView
          description={description}
          document={document}
          statementTerms={statementTerms}
          actionTerms={action.entity_terms}
        />
      )}
      {evidence.length > 0 && (
        <div className="space-y-2">
          {referenceOnly && (
            <h4 className="text-sm font-medium text-success-foreground">
              + {evidence.length === 1 ? 'Reference' : 'References'}
            </h4>
          )}
          <StatementSource
            evidence={evidence}
            activeSourceId={activeSourceId}
            onViewSource={onViewSource}
            onHover={onHover}
          />
        </div>
      )}
      <div className="flex items-center justify-end">
        <DecisionButtons
          decision={decision}
          isSourceVisible={isSourceVisible}
          onDecision={(isAccepted) => onDecision(action, isAccepted)}
        />
      </div>
    </div>
  )
}

// --- Statement item ---

export interface StatementItemViewProps {
  item: StatementItemType
  /** Whether the group title itself already marks this value as proposed. */
  isNewGroup: boolean
  decisions: LocalDecisions
  onDecision: (action: Action, isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover?: (item: StatementItemType) => void
  activeSourceId?: string | null
}

export function StatementItemView({
  item,
  isNewGroup,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
}: StatementItemViewProps) {
  const labelLanguages = useLabelLanguages()

  const document = itemDocument(item)
  const propertyId = document.property.id
  const isDate = propertyId === 'P569' || propertyId === 'P570'
  const entityTerms = item.statement?.entity_terms ?? item.createActions[0]?.entity_terms ?? null

  let content: ReactNode = null
  if (!item.statement) {
    let proposedData: string | null = isNewGroup ? null : 'New statement'
    if (isDate) {
      proposedData = valueDisplay(document.value, entityTerms, labelLanguages)
    } else if (propertyId === 'P39') {
      proposedData = formatTimeframe(parseTimeframe(document.qualifiers))
    }
    const showProposedMarker = !isNewGroup || isDate
    content = proposedData && (
      <div
        className={`font-medium ${showProposedMarker ? 'text-success-foreground' : 'text-foreground-secondary'}`}
      >
        {showProposedMarker && <span aria-hidden="true">+ </span>}
        <span>{proposedData}</span>
      </div>
    )
  } else if (isDate) {
    content = (
      <span className="text-foreground-secondary flex-1">
        {valueDisplay(document.value, entityTerms, labelLanguages)}
      </span>
    )
  } else if (propertyId === 'P39') {
    const timeframe = parseTimeframe(document.qualifiers)
    content = (
      <span
        className={`flex-1 ${timeframe.start === null && timeframe.end === null ? 'text-foreground-subtle italic' : 'text-foreground-secondary'}`}
      >
        {timeframe.start === null && timeframe.end === null
          ? 'No timeframe specified'
          : formatTimeframe(timeframe)}
      </span>
    )
  }

  const actionRowProps = {
    decisions,
    onDecision,
    onViewSource,
    onHover: () => onHover?.(item),
    activeSourceId,
  }

  if (!item.statement) {
    return (
      <div className="space-y-4" onMouseEnter={() => onHover?.(item)}>
        {content}
        <ActionRow
          actions={item.createActions}
          document={document}
          statementTerms={null}
          {...actionRowProps}
        />
      </div>
    )
  }

  const hasNoDataChange = item.editActions.every(
    (action) => describePatch((action.payload as EditStatementPayload).patch) === null,
  )
  const editActionGroups = groupActions(item.editActions)

  return (
    <div className="space-y-3" onMouseEnter={() => onHover?.(item)}>
      {content && hasNoDataChange && (
        <div className="flex items-start gap-4 font-medium">{content}</div>
      )}

      {editActionGroups.map((actions) => (
        <div key={actionGroupKey(actions[0])} className="rounded-md border border-border-muted p-4">
          <ActionRow
            actions={actions}
            document={item.statement.document}
            statementTerms={item.statement.entity_terms}
            {...actionRowProps}
          />
        </div>
      ))}
    </div>
  )
}
