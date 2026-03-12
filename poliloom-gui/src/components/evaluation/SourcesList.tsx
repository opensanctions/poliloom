import { ArchivedPageResponse } from '@/types'
import { Button } from '@/components/ui/Button'

interface SourcesListProps {
  archivedPages: ArchivedPageResponse[]
  activeArchivedPageId: string | null
  onSelect: (page: ArchivedPageResponse) => void
}

export function SourcesList({ archivedPages, activeArchivedPageId, onSelect }: SourcesListProps) {
  return (
    <div className="mb-8">
      <h2 className="text-xl font-semibold text-foreground mb-4">Sources</h2>
      {archivedPages.length === 0 ? (
        <p className="text-sm text-foreground-tertiary">No sources yet</p>
      ) : (
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
      )}
    </div>
  )
}
