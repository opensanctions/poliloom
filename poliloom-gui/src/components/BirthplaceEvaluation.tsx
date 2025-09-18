import { BirthplaceGroup, BirthplaceStatement } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { EvaluationActions } from './EvaluationActions';
import { StatementSource } from './StatementSource';

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
              onHover={() => {
                const firstWithArchive = birthplaceGroup.statements.find(s => s.archived_page);
                if (firstWithArchive) {
                  onHover(firstWithArchive);
                }
              }}
            >
              {birthplaceGroup.statements.map((statement, index) => (
                <div key={statement.id}>
                  {index > 0 && <hr className="border-gray-300 my-2" />}
                  <div className="space-y-2">
                    <div className="flex justify-between items-start gap-4">
                      <span className="text-gray-700 flex-1">Born at location</span>
                      <EvaluationActions
                        statementId={statement.id}
                        hasArchivedPage={!!statement.archived_page}
                        isConfirmed={evaluations.get(statement.id) ?? null}
                        onAction={onAction}
                      />
                    </div>
                    <StatementSource
                      proofLine={statement.proof_line}
                      archivedPage={statement.archived_page}
                      isActive={activeArchivedPageId === statement.archived_page?.id}
                      onShowArchived={() => onShowArchived(statement)}
                      onHover={() => onHover(statement)}
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