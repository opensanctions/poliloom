import { PropertyGroup, PropertyStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { EvaluationActions } from './EvaluationActions';

interface PropertyEvaluationProps {
  properties: PropertyGroup[];
  evaluations: Map<string, boolean>;
  onAction: (propertyId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (property: PropertyStatement) => void;
  onHover: (property: PropertyStatement) => void;
  activeArchivedPageId: string | null;
}

export function PropertyEvaluation({
  properties,
  evaluations,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId
}: PropertyEvaluationProps) {
  if (properties.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Properties</h2>
      <div className="space-y-4">
        {properties.map((propertyGroup) => {
          return (
            <EvaluationItem
              key={propertyGroup.type}
              title={propertyGroup.type}
            >
              {propertyGroup.statements.map((statement, index) => (
                <div key={statement.id}>
                  {index > 0 && <hr className="border-gray-300 my-2" />}
                  <div className="flex justify-between items-center">
                    <span className="text-gray-700">{statement.value}</span>
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