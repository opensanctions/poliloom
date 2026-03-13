import { useState } from 'react'
import { ArchivedPageResponse } from '@/types'
import { Button } from '@/components/ui/Button'
import { AddSourceForm } from './AddSourceForm'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

function SourceStatusIndicator({
  status,
  error,
}: {
  status: ArchivedPageResponse['status']
  error?: string | null
}) {
  if (error) {
    return (
      <span className="text-xs text-red-500" title={error}>
        Failed
      </span>
    )
  }
  if (status === 'PENDING' || status === 'PROCESSING') {
    return (
      <span className="text-xs text-muted-foreground animate-pulse">
        {status === 'PENDING' ? 'Queued' : 'Processing...'}
      </span>
    )
  }
  return null
}

function SourceItem({
  page,
  isActive,
  onSelect,
}: {
  page: ArchivedPageResponse
  isActive: boolean
  onSelect: (page: ArchivedPageResponse) => void
}) {
  const isDone = page.status === 'DONE' && !page.error

  return (
    <div className="flex items-center gap-2">
      <Button
        size="small"
        variant="info"
        active={isActive}
        onClick={() => onSelect(page)}
        className="flex-shrink-0"
        disabled={!isDone}
      >
        {isActive ? 'Viewing' : 'View'}
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
      <SourceStatusIndicator status={page.status} error={page.error} />
    </div>
  )
}

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
          <SourceItem
            key={page.id}
            page={page}
            isActive={activeArchivedPageId === page.id}
            onSelect={onSelect}
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
