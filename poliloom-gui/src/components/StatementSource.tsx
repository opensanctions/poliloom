import { ArchivedPageResponse } from '@/types'
import { Button } from './Button'

interface StatementSourceProps {
  proofLine: string | null
  archivedPage: ArchivedPageResponse | null
  isWikidataStatement: boolean
  isActive: boolean
  onShowArchived: () => void
  onHover: () => void
}

export function StatementSource({
  proofLine,
  archivedPage,
  isWikidataStatement,
  isActive,
  onShowArchived,
  onHover,
}: StatementSourceProps) {
  return (
    <div className="space-y-1" onMouseEnter={onHover}>
      {archivedPage && !isWikidataStatement && (
        <div className="flex items-center gap-2">
          <Button size="sm" variant="info" active={isActive} onClick={onShowArchived}>
            • {isActive ? 'Viewing Source' : 'View Source'}
          </Button>
          <span className="text-sm text-gray-500">{archivedPage.url}</span>
        </div>
      )}
      {proofLine && (
        <div className="text-sm text-gray-600 italic py-2">&quot;{proofLine}&quot;</div>
      )}
    </div>
  )
}
