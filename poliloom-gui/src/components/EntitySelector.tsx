'use client'

import { useState, useEffect, useRef } from 'react'
import { Input } from './Input'
import { Button } from './Button'
import { Spinner } from './Spinner'

export interface SearchResult {
  wikidata_id?: string | null
  name: string
  description?: string
  id?: string
}

interface EntitySelectorProps<T extends SearchResult> {
  searchEndpoint: string
  onSelect: (result: T) => void
  placeholder: string
  label?: string
  selectedEntity: { name: string; id: string } | null
  onClear: () => void
  disabled?: boolean
}

export function EntitySelector<T extends SearchResult>({
  searchEndpoint,
  onSelect,
  placeholder,
  label,
  selectedEntity,
  onClear,
  disabled = false,
}: EntitySelectorProps<T>) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<T[]>([])
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
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    if (!searchQuery.trim()) {
      setSearchResults([])
      setShowDropdown(false)
      setIsSearching(false)
      return
    }

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

  const handleSelect = (result: T) => {
    onSelect(result)
    setShowDropdown(false)
    setSearchResults([])
    setSearchQuery('')
  }

  const handleClear = () => {
    onClear()
    setSearchQuery('')
  }

  // If an entity is selected, show the selected state
  if (selectedEntity) {
    return (
      <div>
        {label && <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}
        <div className="p-3 bg-white border border-gray-300 rounded-md flex justify-between items-center">
          <div>
            <div className="font-medium text-gray-900">{selectedEntity.name}</div>
            <div className="text-sm text-gray-500">{selectedEntity.id}</div>
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={handleClear}
            className="text-sm"
            disabled={disabled}
          >
            Clear
          </Button>
        </div>
      </div>
    )
  }

  // Otherwise, show the search input
  return (
    <div ref={dropdownRef}>
      {label && <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}
      <div className="relative">
        <div className="relative">
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
          />
          {isSearching && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <Spinner />
            </div>
          )}
        </div>

        {showDropdown && (
          <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
            {searchResults.length > 0 ? (
              <ul>
                {searchResults.map((result) => {
                  const resultId = result.wikidata_id || result.id || ''
                  return (
                    <li key={resultId}>
                      <button
                        type="button"
                        onClick={() => handleSelect(result)}
                        className="w-full px-4 py-3 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                      >
                        <div className="font-medium text-gray-900">{result.name}</div>
                        {(result.description || resultId) && (
                          <div className="text-sm text-gray-500">
                            {result.description && `${result.description} `}
                            {resultId && `(${resultId})`}
                          </div>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <div className="px-4 py-3 text-sm text-gray-500">No results found</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
