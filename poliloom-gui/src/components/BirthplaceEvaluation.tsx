import { BirthplaceGroup, BirthplaceStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';

interface BirthplaceEvaluationProps {
  birthplaces: BirthplaceGroup[];
  confirmedBirthplaces: Set<string>;
  discardedBirthplaces: Set<string>;
  onAction: (birthplaceId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (birthplace: BirthplaceStatement) => void;
  onHover: (birthplace: BirthplaceStatement) => void;
  activeArchivedPageId: string | null;
}

export function BirthplaceEvaluation({
  birthplaces,
  confirmedBirthplaces,
  discardedBirthplaces,
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
          const hasAnyConfirmed = birthplaceGroup.statements.some(stmt => confirmedBirthplaces.has(stmt.id));
          const hasAnyDiscarded = birthplaceGroup.statements.some(stmt => discardedBirthplaces.has(stmt.id));
          const firstStatement = birthplaceGroup.statements[0];

          return (
            <EvaluationItem
              key={birthplaceGroup.qid}
              item={firstStatement}
              isConfirmed={hasAnyConfirmed}
              isDiscarded={hasAnyDiscarded}
              onAction={(action) => {
                // Apply action to all statements in this group
                birthplaceGroup.statements.forEach(statement => onAction(statement.id, action));
              }}
              onShowArchived={() => onShowArchived(firstStatement)}
              onHover={() => onHover(firstStatement)}
              isActive={!!(firstStatement.archived_page && activeArchivedPageId === firstStatement.archived_page.id)}
            >
              <h3 className="font-medium text-gray-900 mb-3">
                <a href={`https://www.wikidata.org/wiki/${birthplaceGroup.qid}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {birthplaceGroup.name} <span className="text-gray-500 font-normal">({birthplaceGroup.qid})</span>
                </a>
              </h3>
              <div className="space-y-3">
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
                        <button
                          onClick={() => onAction(statement.id, 'confirm')}
                          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                            confirmedBirthplaces.has(statement.id)
                              ? 'bg-green-600 text-white'
                              : 'bg-green-100 text-green-700 hover:bg-green-200'
                          }`}
                        >
                          ✓
                        </button>
                        <button
                          onClick={() => onAction(statement.id, 'discard')}
                          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                            discardedBirthplaces.has(statement.id)
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