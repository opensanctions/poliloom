interface EvaluationActionsProps {
  statementId: string;
  hasArchivedPage: boolean;
  isConfirmed: boolean | null;
  onAction: (id: string, action: "confirm" | "discard") => void;
}

export function EvaluationActions({
  statementId,
  hasArchivedPage,
  isConfirmed,
  onAction,
}: EvaluationActionsProps) {
  return (
    <div className="flex gap-2">
      {hasArchivedPage ? (
        <button
          onClick={() => onAction(statementId, "confirm")}
          className={`px-2 py-1 text-sm font-medium rounded transition-colors cursor-pointer ${
            isConfirmed === true
              ? "bg-green-600 text-white"
              : "bg-green-100 text-green-700 hover:bg-green-200"
          }`}
        >
          ✓ Confirm
        </button>
      ) : (
        <span className="px-2 py-1 text-sm font-medium text-gray-600 bg-gray-200 rounded">
          Current in Wikidata
        </span>
      )}
      <button
        onClick={() => onAction(statementId, "discard")}
        className={`px-2 py-1 text-sm font-medium rounded transition-colors cursor-pointer ${
          isConfirmed === false
            ? "bg-red-600 text-white"
            : hasArchivedPage
              ? "bg-red-100 text-red-700 hover:bg-red-200"
              : "text-gray-600 bg-gray-200 hover:bg-gray-300"
        }`}
      >
        × Discard
      </button>
    </div>
  );
}
