import type { ReactNode } from 'react'
import type { RestSnak, RestStatement, RestValue } from '@/types'
import { parseTimeValue, timeValue } from '@/lib/wikidata/dateParser'

type Reference = RestStatement['references'][number]

const PROPERTY_LABELS: Record<string, string> = {
  P143: 'Imported from',
  P813: 'Retrieved',
  P854: 'Reference URL',
  P4656: 'Wikimedia import URL',
}

const ENTITY_ID = /^(?:Q\d+|P\d+|L\d+(?:-[FS]\d+)?|E\d+)$/

function externalLink(url: string, children: ReactNode, className = '') {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-accent-foreground hover:underline break-all ${className}`}
    >
      {children}
    </a>
  )
}

function entityLink(entityId: string) {
  const path = entityId.startsWith('P') ? `Property:${entityId}` : entityId
  return externalLink(`https://www.wikidata.org/wiki/${path}`, entityId)
}

function objectContent(value: RestValue): Record<string, unknown> | null {
  if (value.type !== 'value' || typeof value.content !== 'object' || value.content === null) {
    return null
  }
  return value.content as Record<string, unknown>
}

function ReferenceValue({ part }: { part: RestSnak }) {
  const { value } = part
  if (value.type === 'somevalue') return <span>unknown</span>
  if (value.type === 'novalue') return <span>no value</span>

  const time = timeValue(value)
  if (time) {
    // The statement date formatter is Gregorian and does not represent BCE dates.
    if (time.time.startsWith('-')) return <span>{time.time}</span>
    return <span>{parseTimeValue(time).display}</span>
  }

  const content = value.content
  if (typeof content === 'string') {
    if (ENTITY_ID.test(content)) return entityLink(content)
    if (part.property.data_type === 'url' || /^https?:\/\//.test(content)) {
      return externalLink(content, content)
    }
    return <span>{content}</span>
  }

  const object = objectContent(value)
  if (!object) return <span>{String(content)}</span>

  if (typeof object.text === 'string' && typeof object.language === 'string') {
    return (
      <span>
        {object.text} <span className="text-foreground-muted">({object.language})</span>
      </span>
    )
  }

  if (typeof object.amount === 'string') {
    const amount = object.amount.replace(/^\+/, '')
    const unit = typeof object.unit === 'string' && object.unit !== '1' ? object.unit : null
    const unitId = unit?.split('/').pop()
    const bounds =
      typeof object.lowerBound === 'string' || typeof object.upperBound === 'string'
        ? ` [${String(object.lowerBound ?? '')} – ${String(object.upperBound ?? '')}]`
        : ''
    return (
      <span>
        {amount}
        {bounds}
        {unitId && <> {entityLink(unitId)}</>}
      </span>
    )
  }

  if (typeof object.latitude === 'number' && typeof object.longitude === 'number') {
    return (
      <span>
        {object.latitude}, {object.longitude}
      </span>
    )
  }

  return <code className="text-xs break-all">{JSON.stringify(content)}</code>
}

function ReferenceProperty({ property }: { property: RestSnak['property'] }) {
  const label = PROPERTY_LABELS[property.id]
  if (label) return <span>{label}</span>
  return entityLink(property.id)
}

export function ReferenceView({
  reference,
  proposed = false,
}: {
  reference: Reference
  proposed?: boolean
}) {
  return (
    <div
      className={
        proposed
          ? 'rounded-md border border-success-muted bg-success-muted/30 p-3'
          : 'rounded-md border border-border-muted p-3'
      }
    >
      {proposed && (
        <div className="mb-2 text-sm font-medium text-success-foreground">+ Reference</div>
      )}
      {reference.parts.length === 0 ? (
        <p className="text-sm text-foreground-muted">No reference details</p>
      ) : (
        <ul className="space-y-1.5">
          {reference.parts.map((part, index) => (
            <li key={`${part.property.id}-${index}`} className="text-sm">
              <span className="text-foreground-muted">
                <ReferenceProperty property={part.property} />:
              </span>{' '}
              <span className="text-foreground-secondary">
                <ReferenceValue part={part} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
