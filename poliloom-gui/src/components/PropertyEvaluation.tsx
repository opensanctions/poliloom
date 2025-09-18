import { Property, WikidataProperty } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { BaseDisplayItem } from './BaseDisplayItem';

interface PropertyEvaluationProps {
  wikidataProperties: WikidataProperty[];
  extractedProperties: Property[];
  confirmedProperties: Set<string>;
  discardedProperties: Set<string>;
  onAction: (propertyId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (property: Property) => void;
  onHover: (property: Property) => void;
  activeArchivedPageId: string | null;
}

export function PropertyEvaluation({
  wikidataProperties,
  extractedProperties,
  confirmedProperties,
  discardedProperties,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId
}: PropertyEvaluationProps) {
  // Simple merging logic - group by property type
  const mergedMap = new Map<string, { existing?: WikidataProperty; extracted?: Property }>();

  // Add existing properties
  wikidataProperties.forEach(existing => {
    mergedMap.set(existing.type, { existing });
  });

  // Add or merge extracted properties
  extractedProperties.forEach(extracted => {
    const entry = mergedMap.get(extracted.type);
    if (entry) {
      entry.extracted = extracted;
    } else {
      mergedMap.set(extracted.type, { extracted });
    }
  });

  const mergedProperties = Array.from(mergedMap.entries()).map(([type, data]) => ({
    type,
    ...data
  }));

  // Sort by priority: existing-only, conflicted, extracted-only
  mergedProperties.sort((a, b) => {
    const getPriority = (item: typeof a) => {
      if (item.existing && !item.extracted) return 0; // existing-only
      if (item.existing && item.extracted) return 1; // conflicted
      if (!item.existing && item.extracted) return 2; // extracted-only
      return 3; // fallback
    };

    const aPriority = getPriority(a);
    const bPriority = getPriority(b);

    if (aPriority !== bPriority) {
      return aPriority - bPriority;
    }

    return a.type.localeCompare(b.type);
  });

  if (mergedProperties.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Properties</h2>
      <div className="space-y-4">
        {mergedProperties.map((property) => {
          const { existing, extracted } = property;

          // If only extracted data exists, show normal evaluation item
          if (!existing && extracted) {
            return (
              <EvaluationItem
                key={extracted.id}
                item={extracted}
                isConfirmed={confirmedProperties.has(extracted.id)}
                isDiscarded={discardedProperties.has(extracted.id)}
                onAction={(action) => onAction(extracted.id, action)}
                onShowArchived={() => onShowArchived(extracted)}
                onHover={() => onHover(extracted)}
                isActive={!!(extracted.archived_page && activeArchivedPageId === extracted.archived_page.id)}
              >
                <h3 className="font-medium text-gray-900">{extracted.type}</h3>
                <p className="text-gray-700 mt-1">{extracted.value}</p>
              </EvaluationItem>
            );
          }

          // If only existing data exists, show read-only display
          if (existing && !extracted) {
            return (
              <BaseDisplayItem key={existing.id} item={existing}>
                <div>
                  <h3 className="font-medium">{existing.type}</h3>
                  <p className="mt-1">{existing.value}</p>
                </div>
              </BaseDisplayItem>
            );
          }

          // If both exist (conflicted), show comparison with evaluation actions
          if (existing && extracted) {
            return (
              <EvaluationItem
                key={extracted.id}
                item={extracted}
                isConfirmed={confirmedProperties.has(extracted.id)}
                isDiscarded={discardedProperties.has(extracted.id)}
                onAction={(action) => onAction(extracted.id, action)}
                onShowArchived={() => onShowArchived(extracted)}
                onHover={() => onHover(extracted)}
                isActive={!!(extracted.archived_page && activeArchivedPageId === extracted.archived_page.id)}
              >
                <h3 className="font-medium text-gray-900">{extracted.type}</h3>

                {/* Show new value first */}
                <p className="text-gray-700 mt-1">{extracted.value}</p>

                {/* Show existing value with strikethrough underneath if different */}
                {existing.value !== extracted.value && (
                  <p className="text-red-500 line-through text-sm mt-1">
                    Current: {existing.value}
                  </p>
                )}
              </EvaluationItem>
            );
          }

          return null;
        })}
      </div>
    </div>
  );
}