import { useState } from 'react'
import { SourceResponse } from '@/types'
import { Button } from '@/components/ui/Button'
import { AddSourceForm } from './AddSourceForm'
import { SourceItem } from './SourceItem'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

interface SourcesListProps {
  sources: SourceResponse[]
  activeSourceId: string | null
  onViewSource: (sourceId: string) => void
  politicianQid?: string
  onAddSource?: () => void
}

export function SourcesList({
  sources,
  activeSourceId,
  onViewSource,
  politicianQid,
  onAddSource,
}: SourcesListProps) {
  const { isAdvancedMode } = useUserPreferences()
  const [isAdding, setIsAdding] = useState(false)

  const handleAdd = () => {
    onAddSource?.()
    setIsAdding(false)
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-foreground mb-4">Sources</h2>
      <div className="space-y-2">
        {[...sources]
          .sort((a, b) => a.url.localeCompare(b.url))
          .map((page) => (
            <SourceItem
              key={page.id}
              page={page}
              isActive={activeSourceId === page.id}
              onView={() => onViewSource(page.id)}
            />
          ))}
      </div>
      {onAddSource && politicianQid && isAdvancedMode && (
        <div className="mt-4">
          {isAdding ? (
            <AddSourceForm
              politicianQid={politicianQid}
              onAdd={handleAdd}
              onCancel={() => setIsAdding(false)}
            />
          ) : (
            <Button variant="secondary" size="small" onClick={() => setIsAdding(true)}>
              + Add Source
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
