import { PropertyReference, SourceResponse } from '@/types'
import { Button } from '@/components/ui/Button'

interface StatementSourceProps {
  sources: PropertyReference[]
  activeSourceId?: string | null
  sourceById: Map<string, SourceResponse>
  onViewSource?: (sourceId: string, quotes?: string[]) => void
  onHover: () => void
}

export function StatementSource({
  sources,
  activeSourceId,
  sourceById,
  onViewSource,
  onHover,
}: StatementSourceProps) {
  if (sources.length === 0) {
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
                onClick={() => onViewSource?.(ref.source_id, ref.supporting_quotes)}
                className="flex-shrink-0"
                title="Show the source page with highlighted supporting quotes"
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
