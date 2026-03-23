import { useState } from 'react'
import { SourceResponse } from '@/types'
import { Button } from '@/components/ui/Button'
import { AddSourceForm } from './AddSourceForm'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

function SourceStatusIndicator({
  status,
  error,
}: {
  status: SourceResponse['status']
  error?: string | null
}) {
  if (error) {
    return (
      <span className="text-xs text-red-500" title={error}>
        Failed
      </span>
    )
  }
  if (status === 'pending' || status === 'processing') {
    return (
      <span className="text-xs text-muted-foreground animate-pulse">
        {status === 'pending' ? 'Queued' : 'Processing...'}
      </span>
    )
  }
  return null
}

function SourceItem({
  page,
  isActive,
  onViewSource,
}: {
  page: SourceResponse
  isActive: boolean
  onViewSource: (sourceId: string) => void
}) {
  const isDone = page.status === 'done' && !page.error

  return (
    <div className="flex items-center gap-2">
      <Button
        size="small"
        variant="info"
        active={isActive}
        onClick={() => onViewSource(page.id)}
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
              onViewSource={onViewSource}
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
