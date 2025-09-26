import { ArchivedPageResponse } from '@/types';

interface StatementSourceProps {
  proofLine: string | null;
  archivedPage: ArchivedPageResponse | null;
  isWikidataStatement: boolean;
  isActive: boolean;
  onShowArchived: () => void;
  onHover: () => void;
}

export function StatementSource({
  proofLine,
  archivedPage,
  isWikidataStatement,
  isActive,
  onShowArchived,
  onHover
}: StatementSourceProps) {
  return (
    <div className="space-y-1" onMouseEnter={onHover}>
      {archivedPage && !isWikidataStatement && (
        <div className="flex items-center gap-2">
          <button
            onClick={onShowArchived}
            className={`text-sm font-medium px-2 py-1 rounded transition-colors cursor-pointer ${
              isActive
                ? 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
            }`}
          >
            • {isActive ? 'Viewing Source' : 'View Source'}
          </button>
          <span className="text-sm text-gray-500">
            {archivedPage.url}
          </span>
        </div>
      )}
      {proofLine && (
        <div className="text-sm text-gray-600 italic py-1">
          &quot;{proofLine}&quot;
        </div>
      )}
    </div>
  );
}