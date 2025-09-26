import { Property, PropertyType } from '@/types';

export interface PropertyGroup {
  type: PropertyType;
  title: string;
  properties: Property[];
}

/**
 * Groups flat properties array into display sections
 */
export function groupPropertiesForDisplay(properties: Property[]): PropertyGroup[] {
  const groups: PropertyGroup[] = [];

  // Properties section (P569, P570)
  const propertyTypes = [PropertyType.P569, PropertyType.P570];
  const propertyItems = properties.filter(p => propertyTypes.includes(p.type));
  if (propertyItems.length > 0) {
    groups.push({
      type: PropertyType.P569, // Use P569 as representative
      title: 'Properties',
      properties: propertyItems
    });
  }

  // Political Positions section (P39)
  const positionItems = properties.filter(p => p.type === PropertyType.P39);
  if (positionItems.length > 0) {
    groups.push({
      type: PropertyType.P39,
      title: 'Political Positions',
      properties: positionItems
    });
  }

  // Birthplaces section (P19)
  const birthplaceItems = properties.filter(p => p.type === PropertyType.P19);
  if (birthplaceItems.length > 0) {
    groups.push({
      type: PropertyType.P19,
      title: 'Birthplaces',
      properties: birthplaceItems
    });
  }

  // Citizenships section (P27)
  const citizenshipItems = properties.filter(p => p.type === PropertyType.P27);
  if (citizenshipItems.length > 0) {
    groups.push({
      type: PropertyType.P27,
      title: 'Citizenships',
      properties: citizenshipItems
    });
  }

  return groups;
}

/**
 * Gets human-readable label for a property type
 */
export function getPropertyTypeLabel(type: PropertyType): string {
  switch (type) {
    case PropertyType.P569:
      return 'Birth Date';
    case PropertyType.P570:
      return 'Death Date';
    case PropertyType.P19:
      return 'Birthplace';
    case PropertyType.P39:
      return 'Position';
    case PropertyType.P27:
      return 'Citizenship';
    default:
      return type;
  }
}

/**
 * Gets section title for a property group
 */
export function getPropertyGroupTitle(type: PropertyType): string {
  switch (type) {
    case PropertyType.P569:
    case PropertyType.P570:
      return 'Properties';
    case PropertyType.P39:
      return 'Political Positions';
    case PropertyType.P19:
      return 'Birthplaces';
    case PropertyType.P27:
      return 'Citizenships';
    default:
      return 'Other Properties';
  }
}