import { Birthplace, WikidataBirthplace } from '@/types';
import { EvaluationItem } from './EvaluationItem';
import { BaseDisplayItem } from './BaseDisplayItem';

interface BirthplaceEvaluationProps {
  wikidataBirthplaces: WikidataBirthplace[];
  extractedBirthplaces: Birthplace[];
  confirmedBirthplaces: Set<string>;
  discardedBirthplaces: Set<string>;
  onAction: (birthplaceId: string, action: 'confirm' | 'discard') => void;
  onShowArchived: (birthplace: Birthplace) => void;
  onHover: (birthplace: Birthplace) => void;
  activeArchivedPageId: string | null;
}

export function BirthplaceEvaluation({
  wikidataBirthplaces,
  extractedBirthplaces,
  confirmedBirthplaces,
  discardedBirthplaces,
  onAction,
  onShowArchived,
  onHover,
  activeArchivedPageId
}: BirthplaceEvaluationProps) {
  if (wikidataBirthplaces.length === 0 && extractedBirthplaces.length === 0) {
    return null;
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Birthplaces</h2>
      <div className="space-y-4">
        {/* Existing birthplaces */}
        {wikidataBirthplaces.map((birthplace) => (
          <BaseDisplayItem key={birthplace.id} item={birthplace}>
            <div>
              <h3 className="font-medium">
                {birthplace.wikidata_id ? (
                  <a href={`https://www.wikidata.org/wiki/${birthplace.wikidata_id}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    {birthplace.location_name} <span className="text-gray-500 font-normal">({birthplace.wikidata_id})</span>
                  </a>
                ) : birthplace.location_name}
              </h3>
            </div>
          </BaseDisplayItem>
        ))}

        {/* Extracted birthplaces */}
        {extractedBirthplaces.map((birthplace) => (
          <EvaluationItem
            key={birthplace.id}
            item={birthplace}
            isConfirmed={confirmedBirthplaces.has(birthplace.id)}
            isDiscarded={discardedBirthplaces.has(birthplace.id)}
            onAction={(action) => onAction(birthplace.id, action)}
            onShowArchived={() => onShowArchived(birthplace)}
            onHover={() => onHover(birthplace)}
            isActive={!!(birthplace.archived_page && activeArchivedPageId === birthplace.archived_page.id)}
          >
            <h3 className="font-medium text-gray-900">
              {birthplace.wikidata_id ? (
                <a href={`https://www.wikidata.org/wiki/${birthplace.wikidata_id}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {birthplace.location_name} <span className="text-gray-500 font-normal">({birthplace.wikidata_id})</span>
                </a>
              ) : birthplace.location_name}
            </h3>
          </EvaluationItem>
        ))}
      </div>
    </div>
  );
}