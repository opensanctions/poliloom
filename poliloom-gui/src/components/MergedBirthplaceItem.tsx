import { MergedBirthplace, isConflicted, isExtractedOnly, isExistingOnly } from '@/lib/dataMerger';
import { BaseEvaluationItem } from './BaseEvaluationItem';

interface MergedBirthplaceItemProps {
  mergedBirthplace: MergedBirthplace;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
}

export function MergedBirthplaceItem({
  mergedBirthplace,
  isConfirmed,
  isDiscarded,
  onAction,
  onShowArchived,
  onHover,
  isActive = false
}: MergedBirthplaceItemProps) {
  const { existing, extracted } = mergedBirthplace;

  // Helper function to render location title with link
  const renderLocationTitle = (location_name: string, wikidata_id: string | null) => {
    if (wikidata_id) {
      return (
        <a 
          href={`https://www.wikidata.org/wiki/${wikidata_id}`} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="hover:underline"
        >
          {location_name} <span className="text-gray-500 font-normal">({wikidata_id})</span>
        </a>
      );
    }
    return location_name;
  };

  // If only extracted data exists, show normal evaluation item
  if (isExtractedOnly(mergedBirthplace) && extracted) {
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
        <h3 className="font-medium text-gray-900">
          {renderLocationTitle(extracted.location_name, extracted.wikidata_id)}
        </h3>
      </BaseEvaluationItem>
    );
  }

  // If only existing data exists, show read-only display
  if (isExistingOnly(mergedBirthplace) && existing) {
    return (
      <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
        <div className="flex justify-between items-start">
          <div className="flex-1 text-gray-700">
            <h3 className="font-medium">
              {renderLocationTitle(existing.location_name, existing.wikidata_id)}
            </h3>
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

  // If both exist (conflicted), they should match by our merging logic
  // This case handles exact matches that are being confirmed
  if (isConflicted(mergedBirthplace) && existing && extracted) {
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
        <h3 className="font-medium text-gray-900">
          {renderLocationTitle(extracted.location_name, extracted.wikidata_id)}
        </h3>
      </BaseEvaluationItem>
    );
  }

  return null;
}