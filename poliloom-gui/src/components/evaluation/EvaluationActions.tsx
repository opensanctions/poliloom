import { Button } from '@/components/ui/Button'
import { DataLabel } from '@/components/ui/DataLabel'

interface EvaluationActionsProps {
  statementId: string
  isWikidataStatement: boolean
  isUserAdded: boolean
  isAccepted: boolean | null
  isSourceVisible: boolean
  isAdvancedMode: boolean
  onAction?: (id: string, action: 'accept' | 'reject') => void
}

export function EvaluationActions({
  statementId,
  isWikidataStatement,
  isUserAdded,
  isAccepted,
  isSourceVisible,
  isAdvancedMode,
  onAction,
}: EvaluationActionsProps) {
  const showButtons = isWikidataStatement ? isAdvancedMode : isSourceVisible

  return (
    <div className="flex gap-5 items-center ml-auto">
      <DataLabel variant={isWikidataStatement ? 'existing' : 'new'} />
      {showButtons ? (
        <div className="flex gap-2">
          {!isWikidataStatement && (
            <Button
              size="small"
              variant="success"
              active={isAccepted === true}
              onClick={() => onAction?.(statementId, 'accept')}
              title="Mark this data as correct and submit it to Wikidata"
            >
              ✓ Accept
            </Button>
          )}
          <Button
            size="small"
            variant={isWikidataStatement && isAccepted !== false ? 'secondary' : 'danger'}
            active={!isUserAdded && isAccepted === false}
            onClick={() => onAction?.(statementId, 'reject')}
            className={
              isWikidataStatement && isAccepted !== false
                ? '!text-foreground-muted !bg-surface-hover hover:!bg-surface-active'
                : ''
            }
            title={
              isUserAdded
                ? 'Remove this property you added'
                : isWikidataStatement
                  ? 'Mark this existing Wikidata statement as deprecated (incorrect or outdated)'
                  : 'Mark this data as incorrect and prevent it from being submitted'
            }
          >
            {isUserAdded ? '× Remove' : isWikidataStatement ? '↓ Deprecate' : '× Reject'}
          </Button>
        </div>
      ) : !isWikidataStatement ? (
        <div className="flex gap-2">
          {isAccepted === null ? (
            <span className="text-sm text-foreground-muted">View source to evaluate</span>
          ) : (
            <span
              className={`text-sm font-medium ${isAccepted ? 'text-success-foreground' : 'text-danger-foreground'}`}
            >
              {isAccepted ? '✓ Accepted' : '× Rejected'}
            </span>
          )}
        </div>
      ) : null}
    </div>
  )
}
