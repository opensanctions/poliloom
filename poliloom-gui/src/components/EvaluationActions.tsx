import { Button } from './Button'

interface EvaluationActionsProps {
  statementId: string
  isWikidataStatement: boolean
  isConfirmed: boolean | null
  onAction: (id: string, action: 'confirm' | 'discard') => void
}

export function EvaluationActions({
  statementId,
  isWikidataStatement,
  isConfirmed,
  onAction,
}: EvaluationActionsProps) {
  return (
    <div className="flex gap-2">
      {!isWikidataStatement ? (
        <Button
          size="sm"
          variant="success"
          active={isConfirmed === true}
          onClick={() => onAction(statementId, 'confirm')}
        >
          ✓ Confirm
        </Button>
      ) : (
        <span className="px-2 py-1 text-sm font-medium text-gray-500 bg-gray-100 rounded">
          Current in Wikidata
        </span>
      )}
      <Button
        size="sm"
        variant={!isWikidataStatement ? 'danger' : 'secondary'}
        active={isConfirmed === false}
        onClick={() => onAction(statementId, 'discard')}
        className={!isWikidataStatement ? '' : 'text-gray-500 bg-gray-100 hover:bg-gray-300'}
      >
        × Discard
      </Button>
    </div>
  )
}
