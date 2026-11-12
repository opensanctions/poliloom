import { ReactNode } from 'react'
import type {
  Action,
  CreateStatementPayload,
  EditStatementPayload,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  TermMaps,
} from '@/types'
import {
  describePatch,
  effectiveDecision,
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
import { ReferenceView } from './ReferenceView'
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
    case 'reference-append':
      return <ReferenceView reference={description.reference} proposed />
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
  action: Action
  document: Pick<RestStatement, 'qualifiers'>
  statementTerms: TermMaps | null
  statementContent?: ReactNode
  decisions: LocalDecisions
  onDecision: (action: Action, isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover: () => void
  activeSourceId?: string | null
}

function ActionRow({
  action,
  document,
  statementTerms,
  statementContent,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
}: ActionRowProps) {
  const decision = effectiveDecision(action, decisions)
  const isSourceVisible =
    action.evidence.length === 0 || action.evidence.some((e) => e.source.id === activeSourceId)
  const createReferences =
    action.kind === 'CREATE_STATEMENT'
      ? (action.payload as CreateStatementPayload).statement.references
      : []
  const description =
    action.kind === 'EDIT_STATEMENT'
      ? describePatch((action.payload as EditStatementPayload).patch)
      : null

  return (
    <div className="space-y-3">
      {description?.kind === 'reference-append' && statementContent && (
        <div className="flex items-start gap-4 font-medium">{statementContent}</div>
      )}
      {description && (
        <PatchDescriptionView
          description={description}
          document={document}
          statementTerms={statementTerms}
          actionTerms={action.entity_terms}
        />
      )}
      {createReferences.map((reference, index) => (
        <ReferenceView key={reference.hash ?? index} reference={reference} proposed />
      ))}
      {action.evidence.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-foreground-muted">Evidence</h4>
          <StatementSource
            evidence={action.evidence}
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
  decisions: LocalDecisions
  onDecision: (action: Action, isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover?: (item: StatementItemType) => void
  activeSourceId?: string | null
}

export function StatementItemView({
  item,
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
  const entityTerms = item.statement?.entity_terms ?? item.createAction?.entity_terms ?? null

  let content: ReactNode = null
  if (!item.statement) {
    const value = valueDisplay(document.value, entityTerms, labelLanguages)
    content = (
      <div className="text-foreground-secondary">
        <span className="mr-2 font-medium text-success-foreground">+</span>
        <span className="font-medium text-foreground">{value}</span>
        {propertyId === 'P39' && (
          <div className="ml-5 mt-1">{formatTimeframe(parseTimeframe(document.qualifiers))}</div>
        )}
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
      <div
        className="space-y-4 rounded-md border border-border-muted p-4"
        onMouseEnter={() => onHover?.(item)}
      >
        {content}
        <ActionRow
          action={item.createAction}
          document={document}
          statementTerms={null}
          {...actionRowProps}
        />
      </div>
    )
  }

  return (
    <div className="space-y-3" onMouseEnter={() => onHover?.(item)}>
      {content && item.editActions.length === 0 && (
        <div className="flex items-start gap-4 font-medium">{content}</div>
      )}

      {item.editActions.map((action) => (
        <div key={action.id} className="rounded-md border border-border-muted p-4">
          <ActionRow
            action={action}
            document={item.statement.document}
            statementTerms={item.statement.entity_terms}
            statementContent={content}
            {...actionRowProps}
          />
        </div>
      ))}
    </div>
  )
}
