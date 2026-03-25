import { SourceResponse } from '@/types'
import { SourceItem } from './SourceItem'

interface SourcesListProps {
  sources: SourceResponse[]
  activeSourceId: string | null
  onViewSource: (source: SourceResponse) => void
}

export function SourcesList({ sources, activeSourceId, onViewSource }: SourcesListProps) {
  return (
    <div className="mb-4">
      <h2 className="text-xl font-semibold text-foreground mb-4">Sources</h2>
      <div className="space-y-2">
        {[...sources]
          .sort((a, b) => a.url.localeCompare(b.url))
          .map((page) => (
            <SourceItem
              key={page.id}
              page={page}
              isActive={activeSourceId === page.id}
              onView={() => onViewSource(page)}
            />
          ))}
      </div>
    </div>
  )
}
