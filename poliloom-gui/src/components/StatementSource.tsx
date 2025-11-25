import { ArchivedPageResponse } from '@/types'
import { Button } from './Button'

interface StatementSourceProps {
  proofLine: string | null
  archivedPage: ArchivedPageResponse | null
  isWikidataStatement: boolean
  isActive: boolean
  onShowArchived: () => void
  onHover: () => void
}

export function StatementSource({
  proofLine,
  archivedPage,
  isWikidataStatement,
  isActive,
  onShowArchived,
  onHover,
}: StatementSourceProps) {
  return (
    <div className="space-y-1" onMouseEnter={onHover}>
      {archivedPage && !isWikidataStatement && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="info"
            active={isActive}
            onClick={onShowArchived}
            className="flex-shrink-0"
            title="Show the archived source page with highlighted supporting quotes"
          >
            • {isActive ? 'Viewing' : 'View'}
          </Button>
          <a
            href={archivedPage.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline truncate min-w-0"
            title={archivedPage.url}
          >
            {archivedPage.url}
          </a>
        </div>
      )}
      {proofLine && (
        <div className="text-sm text-gray-600 italic py-2">&quot;{proofLine}&quot;</div>
      )}
    </div>
  )
}
