import { Button } from './Button'
import { DataLabel } from './DataLabel'

interface EvaluationActionsProps {
  statementId: string
  isWikidataStatement: boolean
  isAccepted: boolean | null
  onAction?: (id: string, action: 'accept' | 'reject') => void
}

export function EvaluationActions({
  statementId,
  isWikidataStatement,
  isAccepted,
  onAction,
}: EvaluationActionsProps) {
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
      >
        {isWikidataStatement ? '↓ Deprecate' : '× Reject'}
      </Button>
    </div>
  )
}
