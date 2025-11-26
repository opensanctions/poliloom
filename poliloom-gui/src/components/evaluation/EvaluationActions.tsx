import { Button } from '@/components/ui/Button'
import { DataLabel } from '@/components/ui/DataLabel'

interface EvaluationActionsProps {
  statementId: string
  isWikidataStatement: boolean
  isAccepted: boolean | null
  isSourceVisible: boolean
  isAdvancedMode: boolean
  onAction?: (id: string, action: 'accept' | 'reject') => void
}

export function EvaluationActions({
  statementId,
  isWikidataStatement,
  isAccepted,
  isSourceVisible,
  isAdvancedMode,
  onAction,
}: EvaluationActionsProps) {
  // Source not visible only happens for new data (with archived pages)
  if (!isSourceVisible) {
    return (
      <div className="flex gap-2 items-center ml-auto">
        <DataLabel variant="new">New data 🎉</DataLabel>
        <span className="text-sm text-gray-500">View source to evaluate</span>
      </div>
    )
  }

  // For existing Wikidata statements without advanced mode, just show the label
  if (isWikidataStatement && !isAdvancedMode) {
    return (
      <div className="flex gap-2 items-center ml-auto">
        <DataLabel variant="existing">Existing data</DataLabel>
      </div>
    )
  }

  return (
    <div className="flex gap-2 items-center ml-auto">
      {!isWikidataStatement ? (
        <>
          <DataLabel variant="new">New data 🎉</DataLabel>
          <Button
            size="sm"
            variant="success"
            active={isAccepted === true}
            onClick={() => onAction?.(statementId, 'accept')}
            title="Mark this data as correct and submit it to Wikidata"
          >
            ✓ Accept
          </Button>
        </>
      ) : (
        <DataLabel variant="existing">Existing data</DataLabel>
      )}
      <Button
        size="sm"
        variant={isWikidataStatement && isAccepted !== false ? 'secondary' : 'danger'}
        active={isAccepted === false}
        onClick={() => onAction?.(statementId, 'reject')}
        className={
          isWikidataStatement && isAccepted !== false
            ? '!text-gray-500 !bg-gray-100 hover:!bg-gray-300'
            : ''
        }
        title={
          isWikidataStatement
            ? 'Mark this existing Wikidata statement as deprecated (incorrect or outdated)'
            : 'Mark this data as incorrect and prevent it from being submitted'
        }
      >
        {isWikidataStatement ? '↓ Deprecate' : '× Reject'}
      </Button>
    </div>
  )
}
