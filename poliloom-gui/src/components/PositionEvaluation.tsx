import { PositionGroup, PositionStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { DateRange } from './DateRange';
import { EvaluationActions } from './EvaluationActions';
import { StatementSource } from './StatementSource';

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
              onHover={() => {
                const firstWithArchive = positionGroup.statements.find(s => s.archived_page);
                if (firstWithArchive) {
                  onHover(firstWithArchive);
                }
              }}
            >
              {positionGroup.statements.map((statement, index) => (
                <div key={statement.id}>
                  {index > 0 && <hr className="border-gray-300 my-2" />}
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 space-y-1">
                      <DateRange
                        startDate={statement.start_date}
                        endDate={statement.end_date}
                      />
                      <StatementSource
                        proofLine={statement.proof_line}
                        archivedPage={statement.archived_page}
                        isActive={activeArchivedPageId === statement.archived_page?.id}
                        onShowArchived={() => onShowArchived(statement)}
                        onHover={() => onHover(statement)}
                      />
                    </div>
                    <EvaluationActions
                      statementId={statement.id}
                      hasArchivedPage={!!statement.archived_page}
                      isConfirmed={evaluations.get(statement.id) ?? null}
                      onAction={onAction}
                    />
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