import { PropertyReference, SourceResponse } from '@/types'
import { SourceItem } from './SourceItem'

interface StatementSourceProps {
  sources: PropertyReference[]
  activeSourceId?: string | null
  onViewSource?: (source: SourceResponse, quotes?: string[]) => void
  onHover: () => void
}

export function StatementSource({
  sources,
  activeSourceId,
  onViewSource,
  onHover,
}: StatementSourceProps) {
  if (sources.length === 0) {
    return null
  }

  return (
    <div className="space-y-2" onMouseEnter={onHover}>
      {sources
        .toSorted((a, b) => a.source.url.localeCompare(b.source.url))
        .map((ref) => (
          <SourceItem
            key={ref.id}
            page={ref.source}
            isActive={activeSourceId === ref.source.id}
            onView={() => onViewSource?.(ref.source, ref.supporting_quotes)}
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
        ))}
    </div>
  )
}
