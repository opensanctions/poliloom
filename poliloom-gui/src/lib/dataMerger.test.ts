import { describe, it, expect } from 'vitest';
import {
  mergeProperties,
  isConflicted,
  isExtractedOnly,
  isExistingOnly,
  type MergedProperty
} from './dataMerger';
import {
  Property,
  WikidataProperty
} from '@/types';

// Test data
const mockWikidataProperty: WikidataProperty = {
  id: 'wd-1',
  type: 'birth_date',
  value: '1970-01-01'
};

const mockExtractedProperty: Property = {
  id: 'ext-1',
  type: 'birth_date',
  value: '1970-01-02',
  proof_line: 'born on January 2, 1970',
  archived_page: {
    id: 'arch-1',
    url: 'https://example.com',
    content_hash: 'hash123',
    fetch_timestamp: '2024-01-01T00:00:00Z'
  }
};


describe('mergeProperties', () => {
  it('merges existing and extracted properties with same type', () => {
    const result = mergeProperties([mockWikidataProperty], [mockExtractedProperty]);
    
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      key: 'birth_date',
      type: 'birth_date',
      existing: mockWikidataProperty,
      extracted: mockExtractedProperty
    });
  });

  it('returns extracted-only properties when no existing data', () => {
    const result = mergeProperties([], [mockExtractedProperty]);
    
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      key: 'birth_date',
      type: 'birth_date',
      extracted: mockExtractedProperty
    });
    expect(result[0].existing).toBeUndefined();
  });

  it('returns existing-only properties when no extracted data', () => {
    const result = mergeProperties([mockWikidataProperty], []);
    
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      key: 'birth_date',
      type: 'birth_date',
      existing: mockWikidataProperty
    });
    expect(result[0].extracted).toBeUndefined();
  });

  it('handles different property types separately', () => {
    const deathProperty: WikidataProperty = {
      id: 'wd-2',
      type: 'death_date',
      value: '2020-01-01'
    };

    const result = mergeProperties([mockWikidataProperty, deathProperty], [mockExtractedProperty]);
    
    expect(result).toHaveLength(2);
    
    // Should have conflicted birth_date
    const birthDateMerged = result.find(r => r.type === 'birth_date');
    expect(birthDateMerged?.existing).toBeDefined();
    expect(birthDateMerged?.extracted).toBeDefined();
    
    // Should have existing-only death_date
    const deathDateMerged = result.find(r => r.type === 'death_date');
    expect(deathDateMerged?.existing).toBeDefined();
    expect(deathDateMerged?.extracted).toBeUndefined();
  });

  it('sorts properties by priority: existing-only, conflicted, extracted-only', () => {
    const existingOnly: WikidataProperty = {
      id: 'wd-exist',
      type: 'death_date',
      value: '2020-01-01'
    };

    const extractedOnly: Property = {
      id: 'ext-only',
      type: 'nationality',
      value: 'American',
      proof_line: 'nationality American',
      archived_page: mockExtractedProperty.archived_page!
    };

    const result = mergeProperties(
      [mockWikidataProperty, existingOnly],
      [mockExtractedProperty, extractedOnly]
    );
    
    expect(result).toHaveLength(3);
    
    // Priority order: existing-only (death_date), conflicted (birth_date), extracted-only (nationality)
    expect(result[0].type).toBe('death_date'); // existing-only
    expect(result[1].type).toBe('birth_date'); // conflicted
    expect(result[2].type).toBe('nationality'); // extracted-only
  });
});


describe('helper functions', () => {
  const existingOnlyItem: MergedProperty = {
    key: 'test',
    type: 'test',
    existing: mockWikidataProperty
  };

  const extractedOnlyItem: MergedProperty = {
    key: 'test',
    type: 'test',
    extracted: mockExtractedProperty
  };

  const conflictedItem: MergedProperty = {
    key: 'test',
    type: 'test',
    existing: mockWikidataProperty,
    extracted: mockExtractedProperty
  };

  describe('isConflicted', () => {
    it('returns true when both existing and extracted are present', () => {
      expect(isConflicted(conflictedItem)).toBe(true);
    });

    it('returns false when only existing is present', () => {
      expect(isConflicted(existingOnlyItem)).toBe(false);
    });

    it('returns false when only extracted is present', () => {
      expect(isConflicted(extractedOnlyItem)).toBe(false);
    });
  });

  describe('isExtractedOnly', () => {
    it('returns true when only extracted is present', () => {
      expect(isExtractedOnly(extractedOnlyItem)).toBe(true);
    });

    it('returns false when both are present', () => {
      expect(isExtractedOnly(conflictedItem)).toBe(false);
    });

    it('returns false when only existing is present', () => {
      expect(isExtractedOnly(existingOnlyItem)).toBe(false);
    });
  });

  describe('isExistingOnly', () => {
    it('returns true when only existing is present', () => {
      expect(isExistingOnly(existingOnlyItem)).toBe(true);
    });

    it('returns false when both are present', () => {
      expect(isExistingOnly(conflictedItem)).toBe(false);
    });

    it('returns false when only extracted is present', () => {
      expect(isExistingOnly(extractedOnlyItem)).toBe(false);
    });
  });
});