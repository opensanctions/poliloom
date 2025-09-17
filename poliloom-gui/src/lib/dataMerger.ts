import { Property, Position, Birthplace, WikidataProperty, WikidataPosition, WikidataBirthplace } from '@/types';

// Merged data types
export interface MergedProperty {
  key: string; // unique key for the property type
  existing?: WikidataProperty;
  extracted?: Property;
  type: string;
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