import { Position, WikidataPosition } from '@/types';
import { DateRange } from './DateRange';

interface TimeframeItemProps {
  position: Position | WikidataPosition;
  isExisting?: boolean;
  onShowArchived?: () => void;
  onHover?: () => void;
  isActive?: boolean;
}

export function TimeframeItem({
  position,
  isExisting = false,
  onShowArchived,
  onHover,
  isActive = false
}: TimeframeItemProps) {
  const hasArchived = 'archived_page' in position && position.archived_page;

  return (
    <div className="flex justify-between items-center">
      <DateRange
        startDate={position.start_date}
        endDate={position.end_date}
      />
      <div className="flex items-center gap-2">
        {isExisting && (
          <span className="px-2 py-1 text-xs font-medium text-gray-600 bg-gray-200 rounded">
            Current in Wikidata
          </span>
        )}
        {hasArchived && (
          <button
            onClick={onShowArchived}
            onMouseEnter={onHover}
            className={`text-blue-600 hover:text-blue-800 text-sm font-medium px-2 py-1 rounded transition-colors ${
              isActive ? 'bg-blue-100' : 'hover:bg-blue-50'
            }`}
          >
            • View Source
          </button>
        )}
      </div>
    </div>
  );
}