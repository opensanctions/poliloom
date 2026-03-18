import { PropertyReference, SourceResponse } from '@/types'
import { Button } from '@/components/ui/Button'

interface StatementSourceProps {
  sources: PropertyReference[]
  isWikidataStatement: boolean
  activeSourceId?: string | null
  sourceById: Map<string, SourceResponse>
  onShowArchived: (ref: PropertyReference) => void
  onHover: () => void
}

export function StatementSource({
  sources,
  isWikidataStatement,
  activeSourceId,
  sourceById,
  onShowArchived,
  onHover,
}: StatementSourceProps) {
  if (isWikidataStatement || sources.length === 0) {
    return null
  }

  return (
    <div className="space-y-2" onMouseEnter={onHover}>
      {sources.map((ref) => {
        const page = sourceById.get(ref.source_id)
        return (
          <div key={ref.id} className="space-y-1">
            <div className="flex items-center gap-2">
              <Button
                size="small"
                variant="info"
                active={activeSourceId === ref.source_id}
                onClick={() => onShowArchived(ref)}
                className="flex-shrink-0"
                title="Show the archived source page with highlighted supporting quotes"
              >
                • {activeSourceId === ref.source_id ? 'Viewing' : 'View'}
              </Button>
              {page && (
                <a
                  href={page.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-accent-foreground hover:underline truncate min-w-0"
                  title={page.url}
                >
                  {page.url}
                </a>
              )}
            </div>
            {ref.supporting_quotes && ref.supporting_quotes.length > 0 && (
              <ol className="list-decimal list-outside ml-4 space-y-1 py-2">
                {ref.supporting_quotes.map((quote, index) => (
                  <li key={index} className="text-sm text-foreground-tertiary">
                    &quot;{quote}&quot;
                  </li>
                ))}
              </ol>
            )}
          </div>
        )
      })}
    </div>
  )
}
