import { BirthplaceGroup, BirthplaceStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { EvaluationActions } from './EvaluationActions';

interface BirthplaceEvaluationProps {
  birthplaces: BirthplaceGroup[];
  evaluations: Map<string, boolean>;
  onAction: (birthplaceId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (birthplace: BirthplaceStatement) => void;
  onHover: (birthplace: BirthplaceStatement) => void;
  activeArchivedPageId: string | null;
}

export function BirthplaceEvaluation({
  birthplaces,
  evaluations,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId
}: BirthplaceEvaluationProps) {
  if (birthplaces.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Birthplaces</h2>
      <div className="space-y-4">
        {birthplaces.map((birthplaceGroup) => {
          const title = `<a href="https://www.wikidata.org/wiki/${birthplaceGroup.qid}" target="_blank" rel="noopener noreferrer" class="hover:underline">${birthplaceGroup.name} <span class="text-gray-500 font-normal">(${birthplaceGroup.qid})</span></a>`;

          return (
            <EvaluationItem
              key={birthplaceGroup.qid}
              title={title}
            >
              {birthplaceGroup.statements.map((statement, index) => (
                <div key={statement.id}>
                  {index > 0 && <hr className="border-gray-300 my-2" />}
                  <div className="flex justify-between items-center">
                    <span className="text-gray-700">Born at location</span>
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