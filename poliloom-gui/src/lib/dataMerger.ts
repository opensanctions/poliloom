import { Property, Position, Birthplace, WikidataProperty, WikidataPosition, WikidataBirthplace } from '@/types';

// Merged data types
export interface MergedProperty {
  key: string; // unique key for the property type
  existing?: WikidataProperty;
  extracted?: Property;
  type: string;
}

export interface MergedPosition {
  key: string; // unique key combining position_name, wikidata_id, start_date, and end_date
  existing?: WikidataPosition;
  extracted?: Position;
  position_name: string;
  wikidata_id: string | null;
}

export interface MergedBirthplace {
  key: string; // unique key combining location_name and wikidata_id
  existing?: WikidataBirthplace;
  extracted?: Birthplace;
  location_name: string;
  wikidata_id: string | null;
}

// Utility functions for merging data
export function mergeProperties(
  wikidataProperties: WikidataProperty[],
  extractedProperties: Property[]
): MergedProperty[] {
  const mergedMap = new Map<string, MergedProperty>();

  // Add existing properties
  wikidataProperties.forEach(existing => {
    const key = existing.type;
    mergedMap.set(key, {
      key,
      existing,
      type: existing.type
    });
  });

  // Add or merge extracted properties
  extractedProperties.forEach(extracted => {
    const key = extracted.type;
    const existing = mergedMap.get(key);
    
    if (existing) {
      // Merge with existing
      existing.extracted = extracted;
    } else {
      // Add new extracted-only property
      mergedMap.set(key, {
        key,
        extracted,
        type: extracted.type
      });
    }
  });

  const mergedArray = Array.from(mergedMap.values());
  
  // Sort by priority: existing-only, conflicted, extracted-only, then by type name within each group
  return mergedArray.sort((a, b) => {
    
    // Priority order: existing-only (0), conflicted (1), extracted-only (2)
    const getPriority = (item: MergedProperty) => {
      if (isExistingOnly(item)) return 0;
      if (isConflicted(item)) return 1;
      if (isExtractedOnly(item)) return 2;
      return 3; // fallback
    };
    
    const aPriority = getPriority(a);
    const bPriority = getPriority(b);
    
    if (aPriority !== bPriority) {
      return aPriority - bPriority;
    }
    
    // Within same priority group, sort by type name
    return a.type.localeCompare(b.type);
  });
}

export function mergePositions(
  wikidataPositions: WikidataPosition[],
  extractedPositions: Position[]
): MergedPosition[] {
  const mergedMap = new Map<string, MergedPosition>();

  // Add existing positions
  wikidataPositions.forEach(existing => {
    const key = `${existing.position_name}::${existing.wikidata_id || 'null'}::${existing.start_date || 'null'}::${existing.end_date || 'null'}`;
    mergedMap.set(key, {
      key,
      existing,
      position_name: existing.position_name,
      wikidata_id: existing.wikidata_id
    });
  });

  // Add or merge extracted positions
  extractedPositions.forEach(extracted => {
    const key = `${extracted.position_name}::${extracted.wikidata_id || 'null'}::${extracted.start_date || 'null'}::${extracted.end_date || 'null'}`;
    const existing = mergedMap.get(key);
    
    if (existing) {
      // Merge with existing
      existing.extracted = extracted;
    } else {
      // Add new extracted-only position
      mergedMap.set(key, {
        key,
        extracted,
        position_name: extracted.position_name,
        wikidata_id: extracted.wikidata_id
      });
    }
  });

  const mergedArray = Array.from(mergedMap.values());
  
  // Sort by priority: existing-only, conflicted, extracted-only, then by position name within each group
  return mergedArray.sort((a, b) => {
    // Priority order: existing-only (0), conflicted (1), extracted-only (2)
    const getPriority = (item: MergedPosition) => {
      if (isExistingOnly(item)) return 0;
      if (isConflicted(item)) return 1;
      if (isExtractedOnly(item)) return 2;
      return 3; // fallback
    };
    
    const aPriority = getPriority(a);
    const bPriority = getPriority(b);
    
    if (aPriority !== bPriority) {
      return aPriority - bPriority;
    }
    
    // Within same priority group, sort by position name
    return a.position_name.localeCompare(b.position_name);
  });
}

export function mergeBirthplaces(
  wikidataBirthplaces: WikidataBirthplace[],
  extractedBirthplaces: Birthplace[]
): MergedBirthplace[] {
  const mergedMap = new Map<string, MergedBirthplace>();

  // Add existing birthplaces
  wikidataBirthplaces.forEach(existing => {
    const key = `${existing.location_name}::${existing.wikidata_id || 'null'}`;
    mergedMap.set(key, {
      key,
      existing,
      location_name: existing.location_name,
      wikidata_id: existing.wikidata_id
    });
  });

  // Add or merge extracted birthplaces
  extractedBirthplaces.forEach(extracted => {
    const key = `${extracted.location_name}::${extracted.wikidata_id || 'null'}`;
    const existing = mergedMap.get(key);
    
    if (existing) {
      // Merge with existing
      existing.extracted = extracted;
    } else {
      // Add new extracted-only birthplace
      mergedMap.set(key, {
        key,
        extracted,
        location_name: extracted.location_name,
        wikidata_id: extracted.wikidata_id
      });
    }
  });

  const mergedArray = Array.from(mergedMap.values());
  
  // Sort by priority: existing-only, conflicted, extracted-only, then by location name within each group
  return mergedArray.sort((a, b) => {
    // Priority order: existing-only (0), conflicted (1), extracted-only (2)
    const getPriority = (item: MergedBirthplace) => {
      if (isExistingOnly(item)) return 0;
      if (isConflicted(item)) return 1;
      if (isExtractedOnly(item)) return 2;
      return 3; // fallback
    };
    
    const aPriority = getPriority(a);
    const bPriority = getPriority(b);
    
    if (aPriority !== bPriority) {
      return aPriority - bPriority;
    }
    
    // Within same priority group, sort by location name
    return a.location_name.localeCompare(b.location_name);
  });
}

// Helper functions to check merge status
export function isConflicted<T extends { existing?: unknown; extracted?: unknown }>(merged: T): boolean {
  return !!(merged.existing && merged.extracted);
}

export function isExtractedOnly<T extends { existing?: unknown; extracted?: unknown }>(merged: T): boolean {
  return !!(merged.extracted && !merged.existing);
}

export function isExistingOnly<T extends { existing?: unknown; extracted?: unknown }>(merged: T): boolean {
  return !!(merged.existing && !merged.extracted);
}