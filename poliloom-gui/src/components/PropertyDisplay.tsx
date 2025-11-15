import { Property, PropertyType } from '@/types'
import { parseWikidataDate } from '@/lib/wikidata/dateParser'
import { parsePositionQualifiers, formatPositionDates } from '@/lib/wikidata/qualifierParser'
import { EvaluationActions } from './EvaluationActions'
import { StatementSource } from './StatementSource'
import { WikidataMetadata } from './WikidataMetadata'

interface PropertyDisplayProps {
  property: Property
  evaluations: Map<string, boolean>
  onAction?: (propertyId: string, action: 'confirm' | 'discard') => void
  onShowArchived?: (property: Property) => void
  onHover?: (property: Property) => void
  activeArchivedPageId?: string | null
  shouldAutoOpen?: boolean
}

export function PropertyDisplay({
  property,
  evaluations,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId,
  shouldAutoOpen,
}: PropertyDisplayProps) {
  const renderPropertyContent = () => {
    switch (property.type) {
      case PropertyType.P569:
      case PropertyType.P570:
        // Date properties
        if (property.value && property.value_precision) {
          const parsed = parseWikidataDate(property.value, property.value_precision)
          return <span className="text-gray-700 flex-1">{parsed.display}</span>
        }
        return <span className="text-gray-700 flex-1">{property.value || 'Unknown'}</span>

      case PropertyType.P39:
        // Position properties - show only date range since position name is in title
        const dates = property.qualifiers
          ? parsePositionQualifiers(property.qualifiers)
          : { startDate: null, endDate: null }
        const dateRange = formatPositionDates(dates)

        if (dates.startDate === null && dates.endDate === null) {
          return <span className="flex-1 text-gray-400 italic">No timeframe specified</span>
        }
        return <span className="flex-1 text-gray-700">{dateRange}</span>

      case PropertyType.P19:
      case PropertyType.P27:
        // Place/citizenship properties - no content needed as entity name is shown in title
        return <span className="text-gray-700 flex-1"></span>

      default:
        return (
          <span className="text-gray-700 flex-1">
            {property.value || property.entity_name || 'Unknown'}
          </span>
        )
    }
  }

  return (
    <div className="space-y-2" onMouseEnter={() => onHover?.(property)}>
      <div className="flex justify-between items-start gap-4">
        {renderPropertyContent()}
        <EvaluationActions
          statementId={property.key}
          isWikidataStatement={!!property.statement_id}
          isConfirmed={evaluations.get(property.key) ?? null}
          onAction={onAction}
        />
      </div>
      {!property.statement_id && (
        <StatementSource
          proofLine={property.proof_line || null}
          archivedPage={property.archived_page || null}
          isWikidataStatement={!!property.statement_id}
          isActive={activeArchivedPageId === property.archived_page?.id}
          onShowArchived={() => onShowArchived?.(property)}
          onHover={() => onHover?.(property)}
        />
      )}
      <WikidataMetadata
        qualifiers={property.qualifiers}
        references={property.references}
        isDiscarding={!!property.statement_id && evaluations.get(property.key) === false}
        shouldAutoOpen={shouldAutoOpen}
      />
    </div>
  )
}
