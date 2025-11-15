import { ReactNode, Fragment } from 'react'
import { Property, PropertyType } from '@/types'
import { EvaluationItem } from './EvaluationItem'
import { PropertyDisplay } from './PropertyDisplay'
import { EntityLink } from './EntityLink'

interface PropertiesEvaluationProps {
  properties: Property[]
  evaluations: Map<string, boolean>
  onAction: (propertyId: string, action: 'confirm' | 'discard') => void
  onShowArchived: (property: Property) => void
  onHover: (property: Property) => void
  activeArchivedPageId: string | null
}

export function PropertiesEvaluation({
  properties,
  evaluations,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId,
}: PropertiesEvaluationProps) {
  if (properties.length === 0) {
    return null
  }

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

  const getGroupedProperties = () => {
    const sections: Array<{
      title: string
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

      const items = Array.from(dateGroups.entries()).map(([type, props]) => ({
        title: getPropertyTitle(props[0]),
        properties: props,
        key: type,
      }))
      sections.push({ title: 'Properties', items })
    }

    // Process entity-based properties in fixed order (positions, birthplaces, citizenships)
    const orderedPropertyTypes = [PropertyType.P39, PropertyType.P19, PropertyType.P27]

    orderedPropertyTypes.forEach((propertyType) => {
      const typeProperties = entityBasedProps.get(propertyType)
      if (!typeProperties) return

      const sectionTitle = getSectionTitle(propertyType)

      // Group by entity_id
      const entityGroups = new Map<string, Property[]>()
      typeProperties.forEach((property) => {
        const key = property.entity_id!
        if (!entityGroups.has(key)) {
          entityGroups.set(key, [])
        }
        entityGroups.get(key)!.push(property)
      })

      const items = Array.from(entityGroups.entries()).map(([entityKey, entityProperties]) => ({
        title: getPropertyTitle(entityProperties[0]),
        properties: entityProperties,
        key: entityKey,
      }))

      sections.push({ title: sectionTitle, items })
    })

    return sections
  }

  const getSectionTitle = (propertyType: PropertyType): string => {
    switch (propertyType) {
      case PropertyType.P569:
      case PropertyType.P570:
        return 'Properties'
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

  const sections = getGroupedProperties()

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <div key={section.title} className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">{section.title}</h2>
          <div className="space-y-4">
            {section.items.map((item) => (
              <EvaluationItem
                key={item.key}
                title={item.title}
                onHover={() => {
                  const firstWithArchive = item.properties.find(
                    (p) => p.archived_page && !p.statement_id,
                  )
                  if (firstWithArchive) {
                    onHover(firstWithArchive)
                  }
                }}
              >
                {item.properties.map((property, index) => (
                  <Fragment key={property.key}>
                    {index > 0 && <hr className="border-gray-100 my-3" />}
                    <PropertyDisplay
                      property={property}
                      evaluations={evaluations}
                      onAction={onAction}
                      onShowArchived={onShowArchived}
                      onHover={onHover}
                      activeArchivedPageId={activeArchivedPageId}
                    />
                  </Fragment>
                ))}
              </EvaluationItem>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
