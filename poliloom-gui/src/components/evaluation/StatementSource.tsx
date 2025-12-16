import { ArchivedPageResponse } from '@/types'
import { Button } from '@/components/ui/Button'

interface StatementSourceProps {
  supportingQuotes: string[] | null
  archivedPage: ArchivedPageResponse | null
  isWikidataStatement: boolean
  isActive: boolean
  onShowArchived: () => void
  onHover: () => void
}

export function StatementSource({
  supportingQuotes,
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
            size="small"
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
            className="text-sm text-accent-foreground hover:underline truncate min-w-0"
            title={archivedPage.url}
          >
            {archivedPage.url}
          </a>
        </div>
      )}
      {supportingQuotes && supportingQuotes.length > 0 && (
        <ol className="list-decimal list-outside ml-4 space-y-1 py-2">
          {supportingQuotes.map((quote, index) => (
            <li key={index} className="text-sm text-foreground-tertiary">
              &quot;{quote}&quot;
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
