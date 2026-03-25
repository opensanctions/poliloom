import { SourceResponse } from '@/types'
import { SourceItem } from './SourceItem'
import { AddSourceForm } from './AddSourceForm'

interface SourcesSectionProps {
  sources: SourceResponse[]
  activeSourceId: string | null
  onViewSource: (source: SourceResponse) => void
  onAddSource?: (url: string) => Promise<void>
}

export function SourcesSection({
  sources,
  activeSourceId,
  onViewSource,
  onAddSource,
}: SourcesSectionProps) {
  return (
    <div>
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
      {onAddSource && (
        <div className="mt-4">
          <AddSourceForm onSubmit={onAddSource} />
        </div>
      )}
    </div>
  )
}
