import { ReactNode } from 'react'
import type {
  Action,
  ActionEvidence,
  RestValue,
  SourceResponse,
  StatementFact,
  TermMaps,
} from '@/types'
import { proposalEvidence, type ProposalDecisions, type StatementItem } from '@/lib/actions'
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

function factValueDisplay(
  fact: StatementFact,
  terms: TermMaps | null,
  labelLanguages: string[],
): string {
  return fact.property.id === 'P39'
    ? formatTimeframe(parseTimeframe(fact.qualifiers))
    : valueDisplay(fact.value, terms, labelLanguages)
}

function showsFactValue(propertyId: string): boolean {
  return propertyId === 'P39' || propertyId === 'P569' || propertyId === 'P570'
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
  return (
    <InlineDiff
      before={factValueDisplay(before, beforeTerms, labelLanguages)}
      after={factValueDisplay(after, afterTerms, labelLanguages)}
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
        aria-pressed={decision === true}
        onClick={() => onDecision(true)}
        title="Mark this proposal as correct and submit it to Wikidata"
      >
        ✓ Accept
      </Button>
      <Button
        size="small"
        variant="danger"
        active={decision === false}
        aria-pressed={decision === false}
        onClick={() => onDecision(false)}
        title="Mark this proposal as incorrect"
      >
        × Discard
      </Button>
    </div>
  )
}

interface ReviewControls {
  decisions: ProposalDecisions
  onDecision: (proposal: Action[], isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover?: (evidence: ActionEvidence[]) => void
  activeSourceId?: string | null
}

interface ProposalViewProps extends ReviewControls {
  proposal: Action[]
  isNewGroup: boolean
  currentValue: string | null
  currentTerms: TermMaps | null
}

function ProposalView({
  proposal,
  isNewGroup,
  currentValue,
  currentTerms,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
}: ProposalViewProps) {
  const labelLanguages = useLabelLanguages()
  const first = proposal[0]
  const { change, before, after, entity_terms: entityTerms } = first
  const evidence = proposalEvidence(proposal)
  const referenceCount = proposal.reduce(
    (count, action) => count + action.references_to_add.length,
    0,
  )
  const value = showsFactValue(after.property.id)
    ? factValueDisplay(after, entityTerms, labelLanguages)
    : null
  const decision = decisions[first.group_key] ?? null
  const isSourceVisible =
    evidence.length === 0 || evidence.some((entry) => entry.source.id === activeSourceId)

  let content: ReactNode
  switch (change) {
    case 'add': {
      const proposedData = value ?? (isNewGroup ? null : 'New statement')
      content = proposedData && (
        <div
          className={`font-medium ${isNewGroup ? 'text-foreground-secondary' : 'text-success-foreground'}`}
        >
          {!isNewGroup && <span aria-hidden="true">+ </span>}
          <span>{proposedData}</span>
        </div>
      )
      break
    }
    case 'refine':
      if (!before) throw new Error(`Refinement ${first.group_key} has no before fact`)
      content = (
        <FactDiff
          before={before}
          after={after}
          beforeTerms={currentTerms}
          afterTerms={entityTerms}
        />
      )
      break
    case 'reference':
      content = (
        <div>
          <h4 className="text-sm font-medium text-success-foreground">
            <span aria-hidden="true">+ </span>
            <span>{referenceCount === 1 ? 'Add reference' : 'Add references'}</span>
          </h4>
          {value !== null && value !== currentValue && (
            <p className="text-sm text-foreground-secondary">For: {value}</p>
          )}
        </div>
      )
      break
  }

  return (
    <div className="space-y-2">
      {content}
      <StatementSource
        evidence={evidence}
        activeSourceId={activeSourceId}
        onViewSource={onViewSource}
        onHover={() => onHover?.(evidence)}
      />
      <div className="flex items-center justify-end">
        <DecisionButtons
          decision={decision}
          isSourceVisible={isSourceVisible}
          onDecision={(isAccepted) => onDecision(proposal, isAccepted)}
        />
      </div>
    </div>
  )
}

export interface StatementItemViewProps extends ReviewControls {
  item: StatementItem
  /** Whether the group title itself already marks this value as proposed. */
  isNewGroup: boolean
}

export function StatementItemView({ item, isNewGroup, ...controls }: StatementItemViewProps) {
  const labelLanguages = useLabelLanguages()
  const { statement, proposals } = item
  const fact = statement?.document
  const currentTerms = statement?.entity_terms ?? null
  const currentValue =
    fact && showsFactValue(fact.property.id)
      ? factValueDisplay(fact, currentTerms, labelLanguages)
      : null
  const timeframe = fact?.property.id === 'P39' ? parseTimeframe(fact.qualifiers) : null
  const missingTimeframe = timeframe && timeframe.start === null && timeframe.end === null
  const hasRefine = proposals.some((proposal) => proposal[0].change === 'refine')

  return (
    <div className="space-y-3">
      {currentValue !== null && (
        <div
          className={`font-medium ${missingTimeframe ? 'text-foreground-subtle italic' : 'text-foreground-secondary'}`}
        >
          {(hasRefine ? 'Current Wikidata: ' : '') +
            (missingTimeframe ? 'No timeframe specified' : currentValue)}
        </div>
      )}
      {proposals.map((proposal) => (
        <ProposalView
          key={proposal[0].group_key}
          proposal={proposal}
          isNewGroup={isNewGroup}
          currentValue={currentValue}
          currentTerms={currentTerms}
          {...controls}
        />
      ))}
    </div>
  )
}
