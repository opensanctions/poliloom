interface EvaluationActionsProps {
  statementId: string;
  isWikidataStatement: boolean;
  isConfirmed: boolean | null;
  onAction: (id: string, action: "confirm" | "discard") => void;
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
        <span className="px-2 py-1 text-sm font-medium text-gray-500 bg-gray-100 rounded">
          Current in Wikidata
        </span>
      )}
      <button
        onClick={() => onAction(statementId, "discard")}
        className={`px-2 py-1 text-sm font-medium rounded transition-colors cursor-pointer ${
          isConfirmed === false
            ? "bg-red-600 text-white"
            : !isWikidataStatement
              ? "bg-red-100 text-red-700 hover:bg-red-200"
              : "text-gray-600 bg-gray-200 hover:bg-gray-300 hidden"
        }`}
      >
        × Discard
      </button>
    </div>
  );
}
