import { SourceResponse } from '@/types'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { formatSourceError } from './sourceErrors'

interface SourceItemProps {
  page: SourceResponse
  isActive: boolean
  onView: () => void
  label?: string
  activeLabel?: string
  children?: React.ReactNode
}

export function SourceItem({
  page,
  isActive,
  onView,
  label = 'View',
  activeLabel = 'Viewing',
  children,
}: SourceItemProps) {
  const isDone = page.status === 'done' && !page.error
  const isProcessing = !isDone && !page.error

  return (
    <div>
      <div className="flex items-center gap-2">
        <Button
          size="small"
          variant="info"
          active={isActive}
          onClick={onView}
          className="flex-shrink-0"
          disabled={!isDone}
        >
          {isActive ? activeLabel : label}
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
        {isProcessing && (
          <span className="ml-auto flex-shrink-0">
            <Spinner />
          </span>
        )}
        {page.error && (
          <span
            className="ml-auto flex-shrink-0 text-sm text-danger-foreground"
            title={formatSourceError(page.error, page.http_status_code)}
          >
            {formatSourceError(page.error, page.http_status_code)}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}
