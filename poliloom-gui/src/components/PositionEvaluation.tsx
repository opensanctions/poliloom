import { Position, WikidataPosition } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { BaseDisplayItem } from './BaseDisplayItem';
import { DateRange } from './DateRange';

interface PositionEvaluationProps {
  wikidataPositions: WikidataPosition[];
  extractedPositions: Position[];
  confirmedPositions: Set<string>;
  discardedPositions: Set<string>;
  onAction: (positionId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (position: Position) => void;
  onHover: (position: Position) => void;
  activeArchivedPageId: string | null;
}

export function PositionEvaluation({
  wikidataPositions,
  extractedPositions,
  confirmedPositions,
  discardedPositions,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId
}: PositionEvaluationProps) {
  if (wikidataPositions.length === 0 && extractedPositions.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Political Positions</h2>
      <div className="space-y-4">
        {/* Existing positions */}
        {wikidataPositions.map((position) => (
          <BaseDisplayItem key={position.id} item={position}>
            <div>
              <h3 className="font-medium">
                {position.wikidata_id ? (
                  <a href={`https://www.wikidata.org/wiki/${position.wikidata_id}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    {position.position_name} <span className="text-gray-500 font-normal">({position.wikidata_id})</span>
                  </a>
                ) : position.position_name}
              </h3>
              <DateRange
                startDate={position.start_date}
                endDate={position.end_date}
              />
            </div>
          </BaseDisplayItem>
        ))}

        {/* Extracted positions */}
        {extractedPositions.map((position) => (
          <EvaluationItem
            key={position.id}
            item={position}
            isConfirmed={confirmedPositions.has(position.id)}
            isDiscarded={discardedPositions.has(position.id)}
            onAction={(action) => onAction(position.id, action)}
            onShowArchived={() => onShowArchived(position)}
            onHover={() => onHover(position)}
            isActive={!!(position.archived_page && activeArchivedPageId === position.archived_page.id)}
          >
            <h3 className="font-medium text-gray-900">
              {position.wikidata_id ? (
                <a href={`https://www.wikidata.org/wiki/${position.wikidata_id}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {position.position_name} <span className="text-gray-500 font-normal">({position.wikidata_id})</span>
                </a>
              ) : position.position_name}
            </h3>
            <DateRange
              startDate={position.start_date}
              endDate={position.end_date}
            />
          </EvaluationItem>
        ))}
      </div>
    </div>
  );
}