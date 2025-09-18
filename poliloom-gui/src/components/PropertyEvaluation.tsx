import { PropertyGroup, PropertyStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { EvaluationActions } from './EvaluationActions';
import { StatementSource } from './StatementSource';

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
              onHover={() => handleGroupHover(propertyGroup.statements)}
            >
              {propertyGroup.statements.map((statement, index) => (
                <div key={statement.id}>
                  {index > 0 && <hr className="border-gray-300 my-2" />}
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 space-y-1">
                      <span className="text-gray-700">{statement.value}</span>
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