import { PositionGroup, PositionStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { DateRange } from './DateRange';

interface PositionEvaluationProps {
  positions: PositionGroup[];
  confirmedPositions: Set<string>;
  discardedPositions: Set<string>;
  onAction: (positionId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (position: PositionStatement) => void;
  onHover: (position: PositionStatement) => void;
  activeArchivedPageId: string | null;
}

export function PositionEvaluation({
  positions,
  confirmedPositions,
  discardedPositions,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId
}: PositionEvaluationProps) {
  if (positions.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Political Positions</h2>
      <div className="space-y-4">
        {positions.map((positionGroup) => {
          const hasAnyConfirmed = positionGroup.statements.some(stmt => confirmedPositions.has(stmt.id));
          const hasAnyDiscarded = positionGroup.statements.some(stmt => discardedPositions.has(stmt.id));
          const firstStatement = positionGroup.statements[0];

          return (
            <EvaluationItem
              key={positionGroup.qid}
              item={firstStatement}
              isConfirmed={hasAnyConfirmed}
              isDiscarded={hasAnyDiscarded}
              onAction={(action) => {
                // Apply action to all statements in this group
                positionGroup.statements.forEach(statement => onAction(statement.id, action));
              }}
              onShowArchived={() => onShowArchived(firstStatement)}
              onHover={() => onHover(firstStatement)}
              isActive={!!(firstStatement.archived_page && activeArchivedPageId === firstStatement.archived_page.id)}
            >
              <h3 className="font-medium text-gray-900 mb-3">
                <a href={`https://www.wikidata.org/wiki/${positionGroup.qid}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {positionGroup.name} <span className="text-gray-500 font-normal">({positionGroup.qid})</span>
                </a>
              </h3>
              <div className="space-y-3">
                {positionGroup.statements.map((statement, index) => (
                  <div key={statement.id}>
                    {index > 0 && <hr className="border-gray-300 my-2" />}
                    <div className="flex justify-between items-center">
                      <DateRange
                        startDate={statement.start_date}
                        endDate={statement.end_date}
                      />
                      <div className="flex items-center gap-2">
                        {statement.archived_page && (
                          <button
                            onClick={() => onShowArchived(statement)}
                            onMouseEnter={() => onHover(statement)}
                            className={`text-blue-600 hover:text-blue-800 text-sm font-medium px-2 py-1 rounded transition-colors ${
                              statement.archived_page && activeArchivedPageId === statement.archived_page.id
                                ? 'bg-blue-100' : 'hover:bg-blue-50'
                            }`}
                          >
                            • View Source
                          </button>
                        )}
                        <button
                          onClick={() => onAction(statement.id, 'confirm')}
                          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                            confirmedPositions.has(statement.id)
                              ? 'bg-green-600 text-white'
                              : 'bg-green-100 text-green-700 hover:bg-green-200'
                          }`}
                        >
                          ✓
                        </button>
                        <button
                          onClick={() => onAction(statement.id, 'discard')}
                          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                            discardedPositions.has(statement.id)
                              ? 'bg-red-600 text-white'
                              : 'bg-red-100 text-red-700 hover:bg-red-200'
                          }`}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </EvaluationItem>
          );
        })}
      </div>
    </div>
  );
}