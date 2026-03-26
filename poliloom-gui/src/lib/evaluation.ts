import { Property, PropertyActionItem, CreatePropertyItem, PropertyType } from '@/types'
import { parsePositionQualifiers, compareDates } from '@/lib/wikidata/qualifierParser'
import { parseWikidataDate, ParsedWikidataDate } from '@/lib/wikidata/dateParser'

export function actionToEvaluation(actions: PropertyActionItem[], id: string): boolean | undefined {
  const action = actions.find((a) => a.action !== 'create' && a.id === id)
  if (!action) return undefined
  return action.action === 'accept'
}

export function applyAction(
  actions: PropertyActionItem[],
  id: string,
  action: 'accept' | 'reject',
): PropertyActionItem[] {
  // If rejecting a user-added (create) property, remove it
  if (action === 'reject') {
    const createAction = actions.find((a) => a.action === 'create' && a.id === id)
    if (createAction) {
      return actions.filter((a) => a !== createAction)
    }
  }

  const existing = actions.find((a) => a.action !== 'create' && a.id === id)

  if (existing) {
    if (existing.action === action) {
      // Toggle off: same action again removes it
      return actions.filter((a) => a !== existing)
    }
    // Replace: different action
    return actions.map((a) => (a === existing ? { ...a, action } : a)) as PropertyActionItem[]
  }

  // Add new action
  return [...actions, { action, id }]
}

// --- Property grouping ---

export type SectionType = 'date' | PropertyType.P39 | PropertyType.P19 | PropertyType.P27

export interface PropertyGroup {
  key: string
  properties: Property[]
}

export interface PropertySection {
  title: string
  sectionType: SectionType
  groups: PropertyGroup[]
}

function getSectionTitle(propertyType: PropertyType): string {
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

function compareByPrecisionThenDate(a: ParsedWikidataDate, b: ParsedWikidataDate): number {
  if (a.precision !== b.precision) {
    return b.precision - a.precision
  }
  return compareDates(a, b)
}

function getStartDate(property: Property) {
  if (!property.qualifiers) return null
  return parsePositionQualifiers(property.qualifiers).startDate
}

function compareByStartDate(a: Property, b: Property): number {
  const startA = getStartDate(a)
  const startB = getStartDate(b)

  if (!startA && !startB) return 0
  if (!startA) return 1
  if (!startB) return -1

  return compareByPrecisionThenDate(startA, startB)
}

export function groupPropertiesIntoSections(
  properties: Property[],
  options?: { showEmptySections?: boolean },
): PropertySection[] {
  const showEmptySections = options?.showEmptySections ?? false
  const result: PropertySection[] = []

  // Partition into dates and entity-based
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

  // Date section: group by type (P569/P570), sort by precision then value
  if (dateProps.length > 0) {
    const dateGroups = new Map<PropertyType, Property[]>()
    dateProps.forEach((prop) => {
      if (!dateGroups.has(prop.type)) {
        dateGroups.set(prop.type, [])
      }
      dateGroups.get(prop.type)!.push(prop)
    })

    dateGroups.forEach((props) => {
      props.sort((a, b) => {
        if (!a.value || !a.value_precision) return 1
        if (!b.value || !b.value_precision) return -1

        const dateA = parseWikidataDate(a.value, a.value_precision)
        const dateB = parseWikidataDate(b.value, b.value_precision)
        return compareByPrecisionThenDate(dateA, dateB)
      })
    })

    const groups = Array.from(dateGroups.entries()).map(([type, props]) => ({
      key: type,
      properties: props,
    }))
    result.push({ title: 'Properties', sectionType: 'date', groups })
  } else if (showEmptySections) {
    result.push({ title: 'Properties', sectionType: 'date', groups: [] })
  }

  // Entity-based sections in fixed order
  const orderedPropertyTypes = [PropertyType.P39, PropertyType.P19, PropertyType.P27] as const

  orderedPropertyTypes.forEach((propertyType) => {
    const typeProperties = entityBasedProps.get(propertyType)
    if (!typeProperties) {
      if (showEmptySections) {
        result.push({
          title: getSectionTitle(propertyType),
          sectionType: propertyType,
          groups: [],
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

    // Sort within each group, then sort groups by earliest start date
    entityGroups.forEach((props) => props.sort(compareByStartDate))

    const groups = Array.from(entityGroups.entries())
      .map(([entityKey, entityProperties]) => ({
        key: entityKey,
        properties: entityProperties,
      }))
      .sort((a, b) => compareByStartDate(a.properties[0], b.properties[0]))

    result.push({ title: getSectionTitle(propertyType), sectionType: propertyType, groups })
  })

  return result
}

export function getAddLabel(sectionType: SectionType): string {
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

export function createPropertyFromAction(action: CreatePropertyItem): Property {
  return {
    id: action.id,
    type: action.type as PropertyType,
    value: action.value,
    value_precision: action.value_precision,
    entity_id: action.entity_id,
    entity_name: action.entity_name,
    qualifiers: action.qualifiers,
    statement_id: null,
    sources: [],
    userAdded: true,
    evaluation: true,
  }
}
