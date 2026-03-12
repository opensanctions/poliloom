import { useState } from 'react'
import { ArchivedPageResponse } from '@/types'
import { Button } from '@/components/ui/Button'
import { AddSourceForm } from './AddSourceForm'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

interface SourcesListProps {
  archivedPages: ArchivedPageResponse[]
  activeArchivedPageId: string | null
  onSelect: (page: ArchivedPageResponse) => void
  politicianQid?: string
  onAddSource?: (source: ArchivedPageResponse) => void
}

export function SourcesList({
  archivedPages,
  activeArchivedPageId,
  onSelect,
  politicianQid,
  onAddSource,
}: SourcesListProps) {
  const { isAdvancedMode } = useUserPreferences()
  const [isAdding, setIsAdding] = useState(false)

  const handleAdd = (source: ArchivedPageResponse) => {
    onAddSource?.(source)
    setIsAdding(false)
  }

  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-foreground mb-4">Sources</h2>
      <div className="space-y-2">
        {archivedPages.map((page) => (
          <div key={page.id} className="flex items-center gap-2">
            <Button
              size="small"
              variant="info"
              active={activeArchivedPageId === page.id}
              onClick={() => onSelect(page)}
              className="flex-shrink-0"
            >
              {activeArchivedPageId === page.id ? 'Viewing' : 'View'}
            </Button>
            <a
              href={page.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-accent-foreground hover:underline truncate min-w-0"
              title={page.url}
            >
              {page.url}
            </a>
          </div>
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
