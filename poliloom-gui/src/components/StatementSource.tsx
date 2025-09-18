import { ArchivedPageResponse } from '@/types';

interface StatementSourceProps {
  proofLine: string | null;
  archivedPage: ArchivedPageResponse | null;
  isActive: boolean;
  onShowArchived: () => void;
  onHover: () => void;
}

export function StatementSource({
  proofLine,
  archivedPage,
  isActive,
  onShowArchived,
  onHover
}: StatementSourceProps) {
  return (
    <div className="space-y-1" onMouseEnter={onHover}>
      {archivedPage && (
        <div className="flex items-center gap-2">
          <button
            onClick={onShowArchived}
            className={`text-blue-600 hover:text-blue-800 text-sm font-medium px-2 py-1 rounded transition-colors cursor-pointer ${
              isActive ? 'bg-blue-100' : 'hover:bg-blue-50'
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
          "{proofLine}"
        </div>
      )}
    </div>
  );
}