import { ReactNode } from 'react'
import type { Action, RestSnak, RestValue, SourceResponse, StatementFact, TermMaps } from '@/types'
import {
  effectiveDecision,
  groupActions,
  itemFact,
  type LocalDecisions,
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

function timeframeDisplay(qualifiers: RestSnak[]): string {
  return formatTimeframe(parseTimeframe(qualifiers))
}

function FactDiff({
  before,
  after,
  beforeTerms,
  afterTerms,
}: {
  before: StatementFact
  after: StatementFact
  beforeTerms: TermMaps | null
  afterTerms: TermMaps | null
}) {
  const labelLanguages = useLabelLanguages()
  if (after.property.id === 'P39') {
    return (
      <InlineDiff
        before={timeframeDisplay(before.qualifiers)}
        after={timeframeDisplay(after.qualifiers)}
      />
    )
  }
  return (
    <InlineDiff
      before={valueDisplay(before.value, beforeTerms, labelLanguages)}
      after={valueDisplay(after.value, afterTerms, labelLanguages)}
    />
  )
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
  decisions: LocalDecisions
  onDecision: (action: Action, isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover: () => void
  activeSourceId?: string | null
}

function ActionRow({
  action,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
}: ActionRowProps) {
  const decision = effectiveDecision(action, decisions)
  const evidence = action.evidence
  const isSourceVisible =
    evidence.length === 0 || evidence.some((e) => e.source.id === activeSourceId)

  return (
    <div className="space-y-2">
      {evidence.length > 0 && (
        <StatementSource
          evidence={evidence}
          activeSourceId={activeSourceId}
          onViewSource={onViewSource}
          onHover={onHover}
        />
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

  const fact = itemFact(item)
  const propertyId = fact.property.id
  const isDate = propertyId === 'P569' || propertyId === 'P570'
  const entityTerms = item.statement?.entity_terms ?? item.actions[0]?.entity_terms ?? null
  const isAdd = item.actions[0]?.change === 'add'
  const hasRefine = item.actions.some((action) => action.change === 'refine')

  let content: ReactNode = null
  if (!item.statement) {
    if (isAdd) {
      let proposedData: string | null = isNewGroup ? null : 'New statement'
      if (isDate) {
        proposedData = valueDisplay(fact.value, entityTerms, labelLanguages)
      } else if (propertyId === 'P39') {
        proposedData = timeframeDisplay(fact.qualifiers)
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
    }
  } else {
    const contextPrefix = hasRefine ? 'Current Wikidata: ' : ''
    if (isDate) {
      content = (
        <span className="text-foreground-secondary flex-1">
          {contextPrefix + valueDisplay(fact.value, entityTerms, labelLanguages)}
        </span>
      )
    } else if (propertyId === 'P39') {
      const timeframe = parseTimeframe(fact.qualifiers)
      content = (
        <span
          className={`flex-1 ${timeframe.start === null && timeframe.end === null ? 'text-foreground-subtle italic' : 'text-foreground-secondary'}`}
        >
          {contextPrefix +
            (timeframe.start === null && timeframe.end === null
              ? 'No timeframe specified'
              : formatTimeframe(timeframe))}
        </span>
      )
    }
  }

  const actionRowProps = {
    decisions,
    onDecision,
    onViewSource,
    onHover: () => onHover?.(item),
    activeSourceId,
  }

  return (
    <div className="space-y-3" onMouseEnter={() => onHover?.(item)}>
      {content && <div className="flex items-start gap-4 font-medium">{content}</div>}

      {groupActions(item.actions).map((actions) => {
        const first = actions[0]
        return (
          <div key={first.group_key} className="space-y-3">
            {first.change === 'refine' && first.before && (
              <FactDiff
                before={first.before}
                after={first.after}
                beforeTerms={item.statement?.entity_terms ?? null}
                afterTerms={first.entity_terms}
              />
            )}
            {first.change === 'reference' && (
              <div>
                <h4 className="text-sm font-medium text-success-foreground">
                  <span aria-hidden="true">+ </span>
                  <span>Add reference</span>
                </h4>
                {(isDate || propertyId === 'P39') && (
                  <p className="text-sm text-foreground-secondary">
                    {'For: ' +
                      (isDate
                        ? valueDisplay(first.after.value, first.entity_terms, labelLanguages)
                        : timeframeDisplay(first.after.qualifiers))}
                  </p>
                )}
              </div>
            )}
            {actions.map((action) => (
              <ActionRow key={action.id} action={action} {...actionRowProps} />
            ))}
          </div>
        )
      })}
    </div>
  )
}
