import { useState, useLayoutEffect } from 'react'
import { Property, PropertyType, PropertyReference } from '@/types'
import { parseWikidataDate } from '@/lib/wikidata/dateParser'
import { parsePositionQualifiers, formatPositionDates } from '@/lib/wikidata/qualifierParser'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { EvaluationActions } from './EvaluationActions'
import { StatementSource } from './StatementSource'
import { WikidataMetadataButtons, WikidataMetadataPanel } from './WikidataMetadata'

interface PropertyDisplayProps {
  property: Property
  evaluations: Map<string, boolean>
  onAction?: (propertyId: string, action: 'accept' | 'reject') => void
  onShowArchived?: (ref: PropertyReference) => void
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
  const { isAdvancedMode } = useUserPreferences()
  const [openSection, setOpenSection] = useState<'qualifiers' | 'references' | null>(null)
  const [wasAutoOpened, setWasAutoOpened] = useState(false)

  const isDiscarding = evaluations.get(property.key) === false
  const hasQualifiers = property.qualifiers && Object.keys(property.qualifiers).length > 0
  const hasReferences = property.references && property.references.length > 0

  // Auto-open panel when discarding existing Wikidata statements (to show what metadata will be lost)
  useLayoutEffect(() => {
    if (
      shouldAutoOpen &&
      isDiscarding &&
      !!property.statement_id &&
      (hasQualifiers || hasReferences)
    ) {
      if (openSection === null) {
        setWasAutoOpened(true)
        setOpenSection(hasQualifiers ? 'qualifiers' : 'references')
      }
    } else if (!isDiscarding && wasAutoOpened) {
      setOpenSection(null)
      setWasAutoOpened(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldAutoOpen, isDiscarding, hasQualifiers, hasReferences, wasAutoOpened])

  const handleToggle = (section: 'qualifiers' | 'references') => {
    const newOpenSection = openSection === section ? null : section
    setOpenSection(newOpenSection)

    if (newOpenSection !== null) {
      setWasAutoOpened(false)
    }
  }

  const renderPropertyContent = () => {
    switch (property.type) {
      case PropertyType.P569:
      case PropertyType.P570:
        // Date properties
        if (property.value && property.value_precision) {
          const parsed = parseWikidataDate(property.value, property.value_precision)
          return <span className="text-foreground-secondary flex-1">{parsed.display}</span>
        }
        return (
          <span className="text-foreground-secondary flex-1">{property.value || 'Unknown'}</span>
        )

      case PropertyType.P39:
        // Position properties - show only date range since position name is in title
        const dates = property.qualifiers
          ? parsePositionQualifiers(property.qualifiers)
          : { startDate: null, endDate: null }
        const dateRange = formatPositionDates(dates)

        if (dates.startDate === null && dates.endDate === null) {
          return (
            <span className="flex-1 text-foreground-subtle italic">No timeframe specified</span>
          )
        }
        return <span className="flex-1 text-foreground-secondary">{dateRange}</span>

      case PropertyType.P19:
      case PropertyType.P27:
        // Place/citizenship properties - no content needed as entity name is shown in title
        return <span className="text-foreground-secondary flex-1"></span>

      default:
        return (
          <span className="text-foreground-secondary flex-1">
            {property.value || property.entity_name || 'Unknown'}
          </span>
        )
    }
  }

  const hasContent =
    property.type === PropertyType.P569 ||
    property.type === PropertyType.P570 ||
    property.type === PropertyType.P39

  return (
    <div className="space-y-2" onMouseEnter={() => onHover?.(property)}>
      {hasContent && (
        <div className="flex items-start gap-4 mb-3 font-medium">{renderPropertyContent()}</div>
      )}
      {!property.statement_id && (
        <StatementSource
          sources={property.sources}
          isWikidataStatement={!!property.statement_id}
          activeArchivedPageId={activeArchivedPageId}
          onShowArchived={(ref) => onShowArchived?.(ref)}
          onHover={() => onHover?.(property)}
        />
      )}
      <div className="flex items-center gap-4">
        {isDiscarding && property.statement_id && (
          <WikidataMetadataButtons
            qualifiers={property.qualifiers}
            references={property.references}
            openSection={openSection}
            onToggle={handleToggle}
          />
        )}
        <EvaluationActions
          statementId={property.key}
          isWikidataStatement={!!property.statement_id}
          isAccepted={evaluations.get(property.key) ?? null}
          isSourceVisible={
            property.sources.length === 0 ||
            property.sources.some((s) => activeArchivedPageId === s.archived_page.id)
          }
          isAdvancedMode={isAdvancedMode}
          onAction={onAction}
        />
      </div>
      {isDiscarding && property.statement_id && (
        <WikidataMetadataPanel
          qualifiers={property.qualifiers}
          references={property.references}
          openSection={openSection}
        />
      )}
    </div>
  )
}
