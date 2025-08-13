import { MergedPosition, isConflicted, isExtractedOnly, isExistingOnly } from '@/lib/dataMerger';
import { BaseEvaluationItem } from './BaseEvaluationItem';

interface MergedPositionItemProps {
  mergedPosition: MergedPosition;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
}

export function MergedPositionItem({
  mergedPosition,
  isConfirmed,
  isDiscarded,
  onAction,
  onShowArchived,
  onHover,
  isActive = false
}: MergedPositionItemProps) {
  const { existing, extracted } = mergedPosition;

  // Helper function to format date range
  const formatDateRange = (start_date: string | null, end_date: string | null) => {
    return `${start_date || 'Unknown'} - ${end_date || 'Present'}`;
  };

  // Helper function to render position title with link
  const renderPositionTitle = (position_name: string, wikidata_id: string | null) => {
    if (wikidata_id) {
      return (
        <a 
          href={`https://www.wikidata.org/wiki/${wikidata_id}`} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="hover:underline"
        >
          {position_name} <span className="text-gray-500 font-normal">({wikidata_id})</span>
        </a>
      );
    }
    return position_name;
  };

  // If only extracted data exists, show normal evaluation item
  if (isExtractedOnly(mergedPosition) && extracted) {
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
          {renderPositionTitle(extracted.position_name, extracted.wikidata_id)}
        </h3>
        <p className="text-gray-700 mt-1">
          {formatDateRange(extracted.start_date, extracted.end_date)}
        </p>
      </BaseEvaluationItem>
    );
  }

  // If only existing data exists, show read-only display
  if (isExistingOnly(mergedPosition) && existing) {
    return (
      <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
        <div className="flex justify-between items-start">
          <div className="flex-1 text-gray-700">
            <h3 className="font-medium">
              {renderPositionTitle(existing.position_name, existing.wikidata_id)}
            </h3>
            <p className="mt-1">
              {formatDateRange(existing.start_date, existing.end_date)}
            </p>
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
  if (isConflicted(mergedPosition) && existing && extracted) {
    const datesChanged = existing.start_date !== extracted.start_date || existing.end_date !== extracted.end_date;
    
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
          {renderPositionTitle(extracted.position_name, extracted.wikidata_id)}
        </h3>
        
        {/* Show new dates first */}
        <p className="text-gray-700 mt-1">
          {formatDateRange(extracted.start_date, extracted.end_date)}
        </p>
        
        {/* Show existing dates with strikethrough underneath if different */}
        {datesChanged && (
          <p className="text-red-500 line-through text-sm mt-1">
            Current: {formatDateRange(existing.start_date, existing.end_date)}
          </p>
        )}
      </BaseEvaluationItem>
    );
  }

  return null;
}