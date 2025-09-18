import { PositionGroup, PositionStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { DateRange } from './DateRange';
import { EvaluationActions } from './EvaluationActions';

interface PositionEvaluationProps {
  positions: PositionGroup[];
  evaluations: Map<string, boolean>;
  onAction: (positionId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (position: PositionStatement) => void;
  onHover: (position: PositionStatement) => void;
  activeArchivedPageId: string | null;
}

export function PositionEvaluation({
  positions,
  evaluations,
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
          const title = `<a href="https://www.wikidata.org/wiki/${positionGroup.qid}" target="_blank" rel="noopener noreferrer" class="hover:underline">${positionGroup.name} <span class="text-gray-500 font-normal">(${positionGroup.qid})</span></a>`;

          return (
            <EvaluationItem
              key={positionGroup.qid}
              title={title}
            >
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
                      <EvaluationActions
                        statementId={statement.id}
                        hasArchivedPage={!!statement.archived_page}
                        isConfirmed={evaluations.get(statement.id) ?? null}
                        onAction={onAction}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </EvaluationItem>
          );
        })}
      </div>
    </div>
  );
}