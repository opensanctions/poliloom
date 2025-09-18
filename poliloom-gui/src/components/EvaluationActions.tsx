interface EvaluationActionsProps {
  statementId: string;
  hasArchivedPage: boolean;
  isConfirmed: boolean | null;
  onAction: (id: string, action: 'confirm' | 'discard') => void;
}

export function EvaluationActions({
  statementId,
  hasArchivedPage,
  isConfirmed,
  onAction
}: EvaluationActionsProps) {
  return (
    <>
      {hasArchivedPage ? (
        <button
          onClick={() => onAction(statementId, 'confirm')}
          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
            isConfirmed === true
              ? 'bg-green-600 text-white'
              : 'bg-green-100 text-green-700 hover:bg-green-200'
          }`}
        >
          ✓ Confirm
        </button>
      ) : (
        <span className="px-2 py-1 text-xs font-medium text-gray-600 bg-gray-200 rounded">
          Current
        </span>
      )}
      <button
        onClick={() => onAction(statementId, 'discard')}
        className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
          isConfirmed === false
            ? 'bg-red-600 text-white'
            : 'bg-red-100 text-red-700 hover:bg-red-200'
        }`}
      >
        ✕ Discard
      </button>
    </>
  );
}