import { PropertyReference, SourceResponse } from '@/types'
import { SourceItem } from './SourceItem'

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
      {sources
        .map((ref) => ({ ref, page: sourceById.get(ref.source_id) }))
        .sort((a, b) => (a.page?.url ?? '').localeCompare(b.page?.url ?? ''))
        .map(({ ref, page }) => {
          if (!page) return null
          return (
            <SourceItem
              key={ref.id}
              page={page}
              isActive={activeSourceId === ref.source_id}
              onView={() => onViewSource?.(ref.source_id, ref.supporting_quotes)}
              label="• View"
              activeLabel="• Viewing"
            >
              {ref.supporting_quotes && ref.supporting_quotes.length > 0 && (
                <ol className="list-decimal list-outside ml-4 space-y-1 py-2">
                  {ref.supporting_quotes.map((quote, index) => (
                    <li key={index} className="text-sm text-foreground-tertiary">
                      &quot;{quote}&quot;
                    </li>
                  ))}
                </ol>
              )}
            </SourceItem>
          )
        })}
    </div>
  )
}
