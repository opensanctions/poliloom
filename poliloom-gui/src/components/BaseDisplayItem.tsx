import { type BaseItem } from '@/types';
import { ReactNode } from 'react';

interface BaseDisplayItemProps<T extends BaseItem> {
  item: T;
  isConflicted?: boolean;
  children: ReactNode;
}

export function BaseDisplayItem<T extends BaseItem>({
  item: _item,
  isConflicted = false,
  children
}: BaseDisplayItemProps<T>) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
      <div className="flex justify-between items-start">
        <div className={`flex-1 ${isConflicted ? 'line-through text-gray-500' : 'text-gray-700'}`}>
          {children}
        </div>
        <div className="flex items-center ml-4">
          <span className="px-2 py-1 text-xs font-medium text-gray-600 bg-gray-200 rounded">
            Current in Wikidata
          </span>
        </div>
      </div>
    </div>
  );
}