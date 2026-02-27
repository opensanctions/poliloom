import { ReactNode, Fragment, useEffect, useMemo, useState } from 'react'
import { Property, PropertyType, PropertyReference, CreatePropertyItem } from '@/types'
import { EvaluationItem } from './EvaluationItem'
import { PropertyDisplay } from './PropertyDisplay'
import { AddDatePropertyForm } from './AddDatePropertyForm'
import { AddPositionPropertyForm } from './AddPositionPropertyForm'
import { AddEntityPropertyForm } from './AddEntityPropertyForm'
import { EntityLink } from '@/components/ui/EntityLink'
import { Button } from '@/components/ui/Button'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { parsePositionQualifiers, compareDates } from '@/lib/wikidata/qualifierParser'
import { parseWikidataDate } from '@/lib/wikidata/dateParser'

type SectionType = 'date' | PropertyType.P39 | PropertyType.P19 | PropertyType.P27

interface PropertiesEvaluationProps {
  properties: Property[]
  onAction: (propertyId: string, action: 'accept' | 'reject') => void
  onShowArchived: (ref: PropertyReference) => void
  onHover: (property: Property) => void
  activeArchivedPageId: string | null
  onAddProperty?: (property: CreatePropertyItem) => void
}

export function PropertiesEvaluation({
  properties,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId,
  onAddProperty,
}: PropertiesEvaluationProps) {
  const { isAdvancedMode } = useUserPreferences()
  const [addingSection, setAddingSection] = useState<SectionType | null>(null)

  const getPropertyTitle = (property: Property): ReactNode => {
    switch (property.type) {
      case PropertyType.P569:
        return 'Birth Date'
      case PropertyType.P570:
        return 'Death Date'
      case PropertyType.P39:
      case PropertyType.P19:
      case PropertyType.P27:
        return <EntityLink entityId={property.entity_id!} entityName={property.entity_name!} />
      default:
        return property.entity_name || property.entity_id || 'Unknown Property'
    }
  }

  const getSectionTitle = (propertyType: PropertyType): string => {
    switch (propertyType) {
      case PropertyType.P39:
        return 'Political Positions'
      case PropertyType.P19:
        return 'Birthplaces'
      case PropertyType.P27:
        return 'Citizenships'
      default:
        return 'Other Properties'
    }
  }

  const getAddLabel = (sectionType: SectionType): string => {
    switch (sectionType) {
      case 'date':
        return '+ Add Date'
      case PropertyType.P39:
        return '+ Add Position'
      case PropertyType.P19:
        return '+ Add Birthplace'
      case PropertyType.P27:
        return '+ Add Citizenship'
    }
  }

  const sections = useMemo(() => {
    const result: Array<{
      title: string
      sectionType: SectionType
      items: Array<{
        title: ReactNode
        properties: Property[]
        key: string
      }>
    }> = []

    // Collect date properties (birth/death)
    const dateProps: Property[] = []
    const entityBasedProps = new Map<PropertyType, Property[]>()

    properties.forEach((property) => {
      if (property.type === PropertyType.P569 || property.type === PropertyType.P570) {
        dateProps.push(property)
      } else {
        if (!entityBasedProps.has(property.type)) {
          entityBasedProps.set(property.type, [])
        }
        entityBasedProps.get(property.type)!.push(property)
      }
    })

    // Helper to compare parsed dates: precision first (higher wins), then date value
    const compareByPrecisionThenDate = (
      a: { precision: number } & Parameters<typeof compareDates>[0],
      b: { precision: number } & Parameters<typeof compareDates>[0],
    ) => {
      if (a.precision !== b.precision) {
        return b.precision - a.precision
      }
      return compareDates(a, b)
    }

    // Helper to get start date for sorting by qualifiers
    const getStartDate = (property: Property) => {
      if (!property.qualifiers) return null
      return parsePositionQualifiers(property.qualifiers).startDate
    }

    // Helper to compare properties by start date: precision first, then date value
    const compareByStartDate = (a: Property, b: Property) => {
      const startA = getStartDate(a)
      const startB = getStartDate(b)

      if (!startA && !startB) return 0
      if (!startA) return 1
      if (!startB) return -1

      return compareByPrecisionThenDate(startA, startB)
    }

    // Add Properties section (birth and death dates)
    if (dateProps.length > 0) {
      // Group by property type (P569 for birth, P570 for death)
      const dateGroups = new Map<PropertyType, Property[]>()
      dateProps.forEach((prop) => {
        if (!dateGroups.has(prop.type)) {
          dateGroups.set(prop.type, [])
        }
        dateGroups.get(prop.type)!.push(prop)
      })

      // Sort by precision first, then by date value
      dateGroups.forEach((props) => {
        props.sort((a, b) => {
          if (!a.value || !a.value_precision) return 1
          if (!b.value || !b.value_precision) return -1

          const dateA = parseWikidataDate(a.value, a.value_precision)
          const dateB = parseWikidataDate(b.value, b.value_precision)
          return compareByPrecisionThenDate(dateA, dateB)
        })
      })

      const items = Array.from(dateGroups.entries()).map(([type, props]) => ({
        title: getPropertyTitle(props[0]),
        properties: props,
        key: type,
      }))
      result.push({ title: 'Properties', sectionType: 'date', items })
    } else if (isAdvancedMode) {
      result.push({ title: 'Properties', sectionType: 'date', items: [] })
    }

    // Process entity-based properties in fixed order (positions, birthplaces, citizenships)
    const orderedPropertyTypes = [PropertyType.P39, PropertyType.P19, PropertyType.P27] as const

    orderedPropertyTypes.forEach((propertyType) => {
      const typeProperties = entityBasedProps.get(propertyType)
      if (!typeProperties) {
        if (isAdvancedMode) {
          result.push({
            title: getSectionTitle(propertyType),
            sectionType: propertyType,
            items: [],
          })
        }
        return
      }

      // Group by entity_id
      const entityGroups = new Map<string, Property[]>()
      typeProperties.forEach((property) => {
        const key = property.entity_id!
        if (!entityGroups.has(key)) {
          entityGroups.set(key, [])
        }
        entityGroups.get(key)!.push(property)
      })

      // Sort within each group by start date, then sort groups by earliest start date
      entityGroups.forEach((props) => props.sort(compareByStartDate))

      const items = Array.from(entityGroups.entries())
        .map(([entityKey, entityProperties]) => ({
          title: getPropertyTitle(entityProperties[0]),
          properties: entityProperties,
          key: entityKey,
        }))
        .sort((a, b) => compareByStartDate(a.properties[0], b.properties[0]))

      result.push({ title: getSectionTitle(propertyType), sectionType: propertyType, items })
    })

    return result
  }, [properties, isAdvancedMode])

  // Select the first property with sources when properties change
  useEffect(() => {
    for (const section of sections) {
      for (const item of section.items) {
        const firstWithSource = item.properties.find((p) => p.sources.length > 0 && !p.statement_id)
        if (firstWithSource) {
          onShowArchived(firstWithSource.sources[0])
          return
        }
      }
    }
  }, [sections, onShowArchived])

  const handleAdd = (property: CreatePropertyItem) => {
    onAddProperty?.(property)
    setAddingSection(null)
  }

  const renderAddForm = (sectionType: SectionType) => {
    switch (sectionType) {
      case 'date':
        return <AddDatePropertyForm onAdd={handleAdd} onCancel={() => setAddingSection(null)} />
      case PropertyType.P39:
        return <AddPositionPropertyForm onAdd={handleAdd} onCancel={() => setAddingSection(null)} />
      case PropertyType.P19:
        return (
          <AddEntityPropertyForm
            type={PropertyType.P19}
            onAdd={handleAdd}
            onCancel={() => setAddingSection(null)}
          />
        )
      case PropertyType.P27:
        return (
          <AddEntityPropertyForm
            type={PropertyType.P27}
            onAdd={handleAdd}
            onCancel={() => setAddingSection(null)}
          />
        )
    }
  }

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <div key={section.title} className="mb-8">
          <h2 className="text-xl font-semibold text-foreground mb-4">{section.title}</h2>
          <div className="space-y-4">
            {section.items.map((item) => {
              return (
                <EvaluationItem
                  key={item.key}
                  title={item.title}
                  onHover={() => {
                    const firstWithSource = item.properties.find(
                      (p) => p.sources.length > 0 && !p.statement_id,
                    )
                    if (firstWithSource) {
                      onHover(firstWithSource)
                    }
                  }}
                >
                  {item.properties.map((property, index) => (
                    <Fragment key={property.key}>
                      {index > 0 && <hr className="border-border-muted my-3" />}
                      <PropertyDisplay
                        property={property}
                        onAction={onAction}
                        onShowArchived={onShowArchived}
                        onHover={onHover}
                        activeArchivedPageId={activeArchivedPageId}
                        shouldAutoOpen={true}
                      />
                    </Fragment>
                  ))}
                </EvaluationItem>
              )
            })}
          </div>
          {onAddProperty && isAdvancedMode && (
            <div className="mt-4">
              {addingSection === section.sectionType ? (
                renderAddForm(section.sectionType)
              ) : (
                <Button
                  variant="secondary"
                  size="small"
                  onClick={() => setAddingSection(section.sectionType)}
                >
                  {getAddLabel(section.sectionType)}
                </Button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
