import { Button } from './Button'

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
    <div className="flex gap-2 items-center">
      {!isWikidataStatement ? (
        <>
          <span className="px-2 py-1 text-sm font-medium text-indigo-600 bg-indigo-50 rounded">
            New data
          </span>
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
        <span className="px-2 py-1 text-sm font-medium text-gray-500 bg-gray-100 rounded">
          Existing data
        </span>
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
