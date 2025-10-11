'use client'

import { useState, useEffect, useRef } from 'react'
import { Input } from './Input'
import { Spinner } from './Spinner'

export interface EntityItem {
  id: string
  name: string
  wikidataId: string
  startDate?: string
  endDate?: string
}

interface SearchResult {
  wikidata_id: string
  name: string
  description: string
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
  searchEndpoint?: string // e.g., '/api/positions' or '/api/locations'
}

export function EntitySelector({
  label,
  items,
  onItemsChange,
  showQualifiers = false,
  qualifierLabels = { start: 'Start Date', end: 'End Date' },
  searchEndpoint,
}: EntitySelectorProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const searchTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Debounced search
  useEffect(() => {
    // Clear timeout on every change
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    // If no endpoint or empty query, clear results and return early
    if (!searchEndpoint || !searchQuery.trim()) {
      setSearchResults([])
      setShowDropdown(false)
      setIsSearching(false)
      return
    }

    // Set up debounced search
    searchTimeoutRef.current = setTimeout(async () => {
      setIsSearching(true)
      try {
        const response = await fetch(
          `${searchEndpoint}?search=${encodeURIComponent(searchQuery)}&limit=10`,
        )
        if (response.ok) {
          const results = await response.json()
          setSearchResults(results)
          setShowDropdown(results.length > 0)
        }
      } catch (error) {
        console.error('Search failed:', error)
      } finally {
        setIsSearching(false)
      }
    }, 300)

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [searchQuery, searchEndpoint])

  const addEntity = (result: SearchResult) => {
    const newItem: EntityItem = {
      id: crypto.randomUUID(),
      name: result.name,
      wikidataId: result.wikidata_id,
    }
    onItemsChange([...items, newItem])
    setSearchQuery('')
    setShowDropdown(false)
    setSearchResults([])
  }

  const removeItem = (id: string) => {
    onItemsChange(items.filter((item) => item.id !== id))
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

      {/* Search Box */}
      {searchEndpoint && (
        <div className="relative" ref={dropdownRef}>
          <div className="relative">
            <Input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={`Search for ${label.toLowerCase()}...`}
            />
            {isSearching && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <Spinner />
              </div>
            )}
          </div>

          {/* Dropdown */}
          {showDropdown && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
              {searchResults.length > 0 ? (
                <ul>
                  {searchResults.map((result) => (
                    <li key={result.wikidata_id}>
                      <button
                        type="button"
                        onClick={() => addEntity(result)}
                        className="w-full px-4 py-3 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                      >
                        <div className="font-medium text-gray-900">{result.name}</div>
                        <div className="text-sm text-gray-500">
                          {result.description} ({result.wikidata_id})
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-3 text-sm text-gray-500">No results found</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Selected Items */}
      <div className="space-y-4">
        {items.map((item, index) => (
          <div key={item.id} className="p-4 border border-gray-200 rounded-md bg-gray-50">
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-sm font-medium text-gray-700">
                  {label.replace(/s$/, '')} {index + 1}
                </span>
                <div className="mt-1">
                  <div className="font-medium text-gray-900">{item.name}</div>
                  <div className="text-sm text-gray-500">{item.wikidataId}</div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => removeItem(item.id)}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Remove
              </button>
            </div>

            {showQualifiers && (
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-200">
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
                  <label className="block text-sm text-gray-600 mb-1">{qualifierLabels.end}</label>
                  <Input
                    type="date"
                    value={item.endDate || ''}
                    onChange={(e) => updateDate(item.id, 'endDate', e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
