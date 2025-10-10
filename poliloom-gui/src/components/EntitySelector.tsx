'use client'

import { Input } from './Input'

export interface EntityItem {
  id: string
  name: string
  wikidataId: string
  startDate?: string
  endDate?: string
}

interface EntitySelectorProps {
  label: string
  items: EntityItem[]
  onItemsChange: (items: EntityItem[]) => void
  showQualifiers?: boolean
  qualifierLabels?: {
    start: string
    end: string
  }
}

export function EntitySelector({
  label,
  items,
  onItemsChange,
  showQualifiers = false,
  qualifierLabels = { start: 'Start Date', end: 'End Date' },
}: EntitySelectorProps) {
  const addItem = () => {
    const newItem: EntityItem = {
      id: crypto.randomUUID(),
      name: '',
      wikidataId: '',
    }
    onItemsChange([...items, newItem])
  }

  const removeItem = (id: string) => {
    onItemsChange(items.filter((item) => item.id !== id))
  }

  const updateItemName = (id: string, name: string) => {
    const updatedItems = items.map((item) => (item.id === id ? { ...item, name } : item))
    onItemsChange(updatedItems)

    // TODO: Trigger API search when name is typed
  }

  const updateDate = (itemId: string, field: 'startDate' | 'endDate', value: string) => {
    const updatedItems = items.map((item) =>
      item.id === itemId ? { ...item, [field]: value || undefined } : item,
    )
    onItemsChange(updatedItems)
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-medium text-gray-900">{label}</h2>

      <div className="space-y-4">
        {items.map((item, index) => (
          <div key={item.id} className="p-4 border border-gray-200 rounded-md">
            <div className="flex items-start justify-between mb-3">
              <span className="text-sm font-medium text-gray-700">
                {label.replace(/s$/, '')} {index + 1}
              </span>
              {items.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeItem(item.id)}
                  className="text-sm text-red-600 hover:text-red-700"
                >
                  Remove
                </button>
              )}
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Name</label>
                <Input
                  type="text"
                  value={item.name}
                  onChange={(e) => updateItemName(item.id, e.target.value)}
                  placeholder={`Search for ${label.toLowerCase()}...`}
                />
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">Wikidata ID</label>
                <Input
                  type="text"
                  value={item.wikidataId}
                  onChange={(e) => {
                    const updatedItems = items.map((i) =>
                      i.id === item.id ? { ...i, wikidataId: e.target.value } : i,
                    )
                    onItemsChange(updatedItems)
                  }}
                  placeholder="e.g., Q123"
                />
              </div>

              {showQualifiers && (
                <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-200">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      {qualifierLabels.start}
                    </label>
                    <Input
                      type="date"
                      value={item.startDate || ''}
                      onChange={(e) => updateDate(item.id, 'startDate', e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      {qualifierLabels.end}
                    </label>
                    <Input
                      type="date"
                      value={item.endDate || ''}
                      onChange={(e) => updateDate(item.id, 'endDate', e.target.value)}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={addItem}
          className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700"
        >
          Add {label.replace(/s$/, '')}
        </button>
      </div>
    </div>
  )
}
