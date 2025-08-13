import { MergedProperty, isConflicted, isExtractedOnly, isExistingOnly } from '@/lib/dataMerger';
import { BaseEvaluationItem } from './BaseEvaluationItem';

interface MergedPropertyItemProps {
  mergedProperty: MergedProperty;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
}

export function MergedPropertyItem({
  mergedProperty,
  isConfirmed,
  isDiscarded,
  onAction,
  onShowArchived,
  onHover,
  isActive = false
}: MergedPropertyItemProps) {
  const { existing, extracted } = mergedProperty;

  // If only extracted data exists, show normal evaluation item
  if (isExtractedOnly(mergedProperty) && extracted) {
    return (
      <BaseEvaluationItem
        item={extracted}
        isConfirmed={isConfirmed}
        isDiscarded={isDiscarded}
        onAction={onAction}
        onShowArchived={onShowArchived}
        onHover={onHover}
        isActive={isActive}
      >
        <h3 className="font-medium text-gray-900">{extracted.type}</h3>
        <p className="text-gray-700 mt-1">{extracted.value}</p>
      </BaseEvaluationItem>
    );
  }

  // If only existing data exists, show read-only display
  if (isExistingOnly(mergedProperty) && existing) {
    return (
      <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
        <div className="flex justify-between items-start">
          <div className="flex-1 text-gray-700">
            <h3 className="font-medium">{existing.type}</h3>
            <p className="mt-1">{existing.value}</p>
          </div>
          <div className="flex items-center ml-4">
            <span className="px-2 py-1 text-xs font-medium text-gray-600 bg-gray-200 rounded">
              Current in Wikidata
            </span>
          </div>
        </div>
      </div>
    );
  }

  // If both exist (conflicted), show comparison with evaluation actions
  if (isConflicted(mergedProperty) && existing && extracted) {
    return (
      <BaseEvaluationItem
        item={extracted}
        isConfirmed={isConfirmed}
        isDiscarded={isDiscarded}
        onAction={onAction}
        onShowArchived={onShowArchived}
        onHover={onHover}
        isActive={isActive}
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
      </BaseEvaluationItem>
    );
  }

  return null;
}