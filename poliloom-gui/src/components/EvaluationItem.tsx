import { type BaseEvaluationItem } from '@/types';
import { ReactNode } from 'react';

interface EvaluationItemProps<T extends BaseEvaluationItem> {
  item: T;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
  children: ReactNode;
}

export function EvaluationItem<T extends BaseEvaluationItem>({
  item,
  isConfirmed,
  isDiscarded,
  onAction,
  onShowArchived,
  onHover,
  isActive = false,
  children
}: EvaluationItemProps<T>) {
  return (
    <div 
      className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
      onMouseEnter={onHover}
    >
      <div className="flex justify-between items-start">
        <div className="flex-1">
          {children}
          {item.archived_page && (
            <div className="mt-2">
              <button
                onClick={onShowArchived}
                className={`text-sm inline-block mr-3 ${
                  isActive 
                    ? 'bg-blue-100 text-blue-800 px-2 py-1 rounded border border-blue-300 font-medium'
                    : 'text-blue-600 hover:text-blue-800'
                }`}
              >
                {isActive ? '● Viewing Source' : 'View Source →'}
              </button>
              <span className="text-gray-500 text-xs">
                From: {item.archived_page.url}
              </span>
            </div>
          )}
        </div>
        <div className="flex space-x-2 ml-4">
          <button
            onClick={() => onAction('confirm')}
            className={`px-3 py-1 rounded text-sm font-medium cursor-pointer ${
              isConfirmed
                ? 'bg-green-100 text-green-800 border border-green-300'
                : 'bg-gray-100 text-gray-700 hover:bg-green-50 hover:text-green-700'
            }`}
          >
            ✓ Confirm
          </button>
          <button
            onClick={() => onAction('discard')}
            className={`px-3 py-1 rounded text-sm font-medium cursor-pointer ${
              isDiscarded
                ? 'bg-red-100 text-red-800 border border-red-300'
                : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-700'
            }`}
          >
            ✗ Discard
          </button>
        </div>
      </div>
      {item.proof_line && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-gray-600 text-sm italic">Evidence: {item.proof_line}</p>
        </div>
      )}
    </div>
  );
}