import { Fragment, ReactNode, useState } from 'react'
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
  type LocalDecisions,
  type PatchDescription,
  type StatementItem as StatementItemType,
} from '@/lib/actions'
import { best_label } from '@/lib/labels'
import { parseTimeValue, timeValue } from '@/lib/wikidata/dateParser'
import { formatTimeframe, parseTimeframe } from '@/lib/wikidata/qualifierParser'
import { Button } from '@/components/ui/Button'
import { DataLabel } from '@/components/ui/DataLabel'
import { StatementSource } from './StatementSource'
import { WikidataMetadataButtons, WikidataMetadataPanel } from './WikidataMetadata'

function itemDocument(item: StatementItemType): Omit<RestStatement, 'id'> {
  if (item.statement) return item.statement.document
  if (item.createAction.kind !== 'CREATE_STATEMENT') {
    throw new Error(`Expected CREATE_STATEMENT action, got ${item.createAction.kind}`)
  }
  return (item.createAction.payload as CreateStatementPayload).statement
}

// --- Value and snak display ---

function valueDisplay(
  value: RestValue,
  terms: TermMaps | null,
  userLanguageCodes: string[],
): string {
  const time = timeValue(value)
  if (time) return parseTimeValue(time).display
  if (value.type === 'value') {
    if (typeof value.content === 'string' && value.content.startsWith('Q')) {
      return best_label(terms, userLanguageCodes, value.content)
    }
    return String(value.content)
  }
  return value.type === 'somevalue' ? 'unknown' : 'no value'
}

function snakDisplay(snak: RestSnak): string {
  return valueDisplay(snak.value, null, [])
}

// --- Edit patch descriptions ---

function PatchDescriptionView({
  description,
  entityTerms,
  userLanguageCodes,
}: {
  description: PatchDescription
  entityTerms: TermMaps | null
  userLanguageCodes: string[]
}) {
  switch (description.kind) {
    case 'value-refinement':
      return (
        <span className="text-foreground-secondary">
          Value: {valueDisplay(description.oldValue, null, userLanguageCodes)}{' '}
          <span aria-hidden="true">→</span>{' '}
          {valueDisplay(description.newValue, entityTerms, userLanguageCodes)}
        </span>
      )
    case 'qualifier-refinement':
      return (
        <span className="text-foreground-secondary">
          Qualifier {description.newQualifier.property.id}: {snakDisplay(description.oldQualifier)}{' '}
          <span aria-hidden="true">→</span> {snakDisplay(description.newQualifier)}
        </span>
      )
    case 'qualifier-append':
      return (
        <span className="text-foreground-secondary">
          New qualifier {description.qualifier.property.id}: {snakDisplay(description.qualifier)}
        </span>
      )
    case 'reference-append':
      return (
        <span className="text-foreground-secondary">
          New reference:{' '}
          {description.reference.parts
            .map((part) => `${part.property.id}: ${snakDisplay(part)}`)
            .join(', ')}
        </span>
      )
  }
}

// --- Decision controls ---

function DecisionButtons({
  action,
  decision,
  isSourceVisible,
  onDecision,
}: {
  action: Action
  decision: boolean | null
  isSourceVisible: boolean
  onDecision: (action: Action, isAccepted: boolean) => void
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
        onClick={() => onDecision(action, true)}
        title="Mark this proposal as correct and submit it to Wikidata"
      >
        ✓ Accept
      </Button>
      <Button
        size="small"
        variant="danger"
        active={decision === false}
        onClick={() => onDecision(action, false)}
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
  showLabel: boolean
  decisions: LocalDecisions
  onDecision: (action: Action, isAccepted: boolean) => void
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover: () => void
  activeSourceId?: string | null
  userLanguageCodes: string[]
}

function ActionRow({
  action,
  showLabel,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
  userLanguageCodes,
}: ActionRowProps) {
  const decision = effectiveDecision(action, decisions)
  const isSourceVisible =
    action.evidence.length === 0 || action.evidence.some((e) => e.source.id === activeSourceId)

  return (
    <div className="space-y-2">
      {action.kind === 'EDIT_STATEMENT' && (
        <PatchDescriptionView
          description={describePatch((action.payload as EditStatementPayload).patch)}
          entityTerms={action.entity_terms}
          userLanguageCodes={userLanguageCodes}
        />
      )}
      <StatementSource
        evidence={action.evidence}
        activeSourceId={activeSourceId}
        onViewSource={onViewSource}
        onHover={onHover}
      />
      <div className="flex items-center gap-4">
        <div className="flex gap-5 items-center ml-auto">
          {showLabel && <DataLabel variant="new" />}
          <DecisionButtons
            action={action}
            decision={decision}
            isSourceVisible={isSourceVisible}
            onDecision={onDecision}
          />
        </div>
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
  userLanguageCodes: string[]
}

export function StatementItemView({
  item,
  decisions,
  onDecision,
  onViewSource,
  onHover,
  activeSourceId,
  userLanguageCodes,
}: StatementItemViewProps) {
  const [openSection, setOpenSection] = useState<'qualifiers' | 'references' | null>(null)

  const handleToggle = (section: 'qualifiers' | 'references') => {
    setOpenSection((prev) => (prev === section ? null : section))
  }

  const document = itemDocument(item)
  const propertyId = document.property.id
  const isDate = propertyId === 'P569' || propertyId === 'P570'
  const entityTerms = item.statement?.entity_terms ?? item.createAction?.entity_terms ?? null

  let content: ReactNode = null
  if (isDate) {
    content = (
      <span className="text-foreground-secondary flex-1">
        {valueDisplay(document.value, entityTerms, userLanguageCodes)}
      </span>
    )
  } else if (propertyId === 'P39') {
    const timeframe = parseTimeframe(document.qualifiers)
    if (timeframe.start === null && timeframe.end === null) {
      content = <span className="flex-1 text-foreground-subtle italic">No timeframe specified</span>
    } else {
      content = (
        <span className="flex-1 text-foreground-secondary">{formatTimeframe(timeframe)}</span>
      )
    }
  }

  const actionRowProps = {
    decisions,
    onDecision,
    onViewSource,
    onHover: () => onHover?.(item),
    activeSourceId,
    userLanguageCodes,
  }

  return (
    <div className="space-y-2" onMouseEnter={() => onHover?.(item)}>
      {content && <div className="flex items-start gap-4 mb-3 font-medium">{content}</div>}

      {item.statement ? (
        <>
          <div className="flex items-center gap-4">
            <WikidataMetadataButtons
              qualifiers={document.qualifiers}
              references={document.references}
              openSection={openSection}
              onToggle={handleToggle}
            />
            <div className="flex gap-5 items-center ml-auto">
              <DataLabel variant="existing" />
            </div>
          </div>
          <WikidataMetadataPanel
            qualifiers={document.qualifiers}
            references={document.references}
            openSection={openSection}
          />
          {item.editActions.map((action, index) => (
            <Fragment key={action.id}>
              {index > 0 && <hr className="border-border-muted my-3" />}
              <ActionRow action={action} showLabel={false} {...actionRowProps} />
            </Fragment>
          ))}
        </>
      ) : (
        <ActionRow action={item.createAction} showLabel={true} {...actionRowProps} />
      )}
    </div>
  )
}
