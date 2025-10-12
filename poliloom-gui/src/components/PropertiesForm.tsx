'use client'

import { useState, useEffect, useRef } from 'react'
import { Property, PropertyType } from '@/types'
import { Input } from './Input'
import { Button } from './Button'
import { Spinner } from './Spinner'

interface PropertiesFormProps {
  properties: Property[]
  onPropertiesChange: (properties: Property[]) => void
}

interface SearchResult {
  wikidata_id: string
  name: string
  description: string
}

interface EntitySearchProps {
  searchEndpoint: string
  onSelect: (result: SearchResult) => void
  placeholder: string
}

function EntitySearch({ searchEndpoint, onSelect, placeholder }: EntitySearchProps) {
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

  const handleSelect = (result: SearchResult) => {
    onSelect(result)
    setSearchQuery('')
    setShowDropdown(false)
    setSearchResults([])
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <Input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={placeholder}
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
              {searchResults.map((result) => (
                <li key={result.wikidata_id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(result)}
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
  )
}

export function PropertiesForm({ properties, onPropertiesChange }: PropertiesFormProps) {
  // Helper functions to extract properties by type
  const getPropertiesByType = (type: PropertyType) => {
    return properties.filter((p) => p.type === type)
  }

  const addProperty = (property: Property) => {
    onPropertiesChange([...properties, property])
  }

  const updateProperty = (id: string, updates: Partial<Property>) => {
    onPropertiesChange(properties.map((p) => (p.id === id ? { ...p, ...updates } : p)))
  }

  const removeProperty = (id: string) => {
    onPropertiesChange(properties.filter((p) => p.id !== id))
  }

  // Date helpers
  const wikidataDateToHtml = (wikidataDate: string): string => {
    // Convert +YYYY-MM-DDT00:00:00Z to YYYY-MM-DD
    const match = wikidataDate.match(/\+?(\d{4})-(\d{2})-(\d{2})/)
    return match ? `${match[1]}-${match[2]}-${match[3]}` : ''
  }

  const htmlDateToWikidata = (htmlDate: string): string => {
    // Convert YYYY-MM-DD to +YYYY-MM-DDT00:00:00Z
    const [year, month, day] = htmlDate.split('-')
    return `+${year}-${month}-${day}T00:00:00Z`
  }

  const birthDates = getPropertiesByType(PropertyType.P569)
  const deathDates = getPropertiesByType(PropertyType.P570)
  const positions = getPropertiesByType(PropertyType.P39)
  const birthplaces = getPropertiesByType(PropertyType.P19)
  const citizenships = getPropertiesByType(PropertyType.P27)

  return (
    <div className="space-y-8">
      {/* Birth Date */}
      <div className="space-y-4">
        <h2 className="text-lg font-medium text-gray-900">Birth Date</h2>
        {birthDates.map((birthDate) => (
          <div key={birthDate.id} className="p-4 border border-gray-200 rounded-md bg-gray-50">
            <div className="flex gap-3 mb-3">
              <Input
                type="date"
                value={birthDate.value ? wikidataDateToHtml(birthDate.value) : ''}
                onChange={(e) =>
                  updateProperty(birthDate.id, {
                    value: e.target.value ? htmlDateToWikidata(e.target.value) : undefined,
                  })
                }
                className="flex-1"
              />
              <select
                value={birthDate.value_precision ?? 11}
                onChange={(e) =>
                  updateProperty(birthDate.id, { value_precision: Number(e.target.value) })
                }
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
              >
                <option value={11}>Day</option>
                <option value={10}>Month</option>
                <option value={9}>Year</option>
              </select>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => removeProperty(birthDate.id)}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Remove
            </Button>
          </div>
        ))}
        {birthDates.length === 0 && (
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              addProperty({
                id: crypto.randomUUID(),
                type: PropertyType.P569,
                value: undefined,
                value_precision: 11,
              })
            }
          >
            Add Birth Date
          </Button>
        )}
      </div>

      {/* Death Date */}
      <div className="space-y-4">
        <h2 className="text-lg font-medium text-gray-900">Death Date</h2>
        {deathDates.map((deathDate) => (
          <div key={deathDate.id} className="p-4 border border-gray-200 rounded-md bg-gray-50">
            <div className="flex gap-3 mb-3">
              <Input
                type="date"
                value={deathDate.value ? wikidataDateToHtml(deathDate.value) : ''}
                onChange={(e) =>
                  updateProperty(deathDate.id, {
                    value: e.target.value ? htmlDateToWikidata(e.target.value) : undefined,
                  })
                }
                className="flex-1"
              />
              <select
                value={deathDate.value_precision ?? 11}
                onChange={(e) =>
                  updateProperty(deathDate.id, { value_precision: Number(e.target.value) })
                }
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
              >
                <option value={11}>Day</option>
                <option value={10}>Month</option>
                <option value={9}>Year</option>
              </select>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => removeProperty(deathDate.id)}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Remove
            </Button>
          </div>
        ))}
        {deathDates.length === 0 && (
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              addProperty({
                id: crypto.randomUUID(),
                type: PropertyType.P570,
                value: undefined,
                value_precision: 11,
              })
            }
          >
            Add Death Date
          </Button>
        )}
      </div>

      {/* Political Positions */}
      <div className="space-y-4">
        <h2 className="text-lg font-medium text-gray-900">Political Positions</h2>
        <EntitySearch
          searchEndpoint="/api/positions"
          placeholder="Search for positions..."
          onSelect={(result) =>
            addProperty({
              id: crypto.randomUUID(),
              type: PropertyType.P39,
              entity_id: result.wikidata_id,
              entity_name: result.name,
              qualifiers: {},
            })
          }
        />
        {positions.map((position) => (
          <div key={position.id} className="p-4 border border-gray-200 rounded-md bg-gray-50">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-medium text-gray-900">{position.entity_name}</div>
                <div className="text-sm text-gray-500">{position.entity_id}</div>
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => removeProperty(position.id)}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Remove
              </Button>
            </div>

            {/* Qualifiers - Start and End Dates */}
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-gray-200">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Start Date</label>
                <div className="flex gap-2">
                  <Input
                    type="date"
                    value={
                      position.qualifiers?.P580?.[0]?.datavalue?.value?.time
                        ? wikidataDateToHtml(
                            position.qualifiers.P580[0].datavalue.value.time as string,
                          )
                        : ''
                    }
                    onChange={(e) => {
                      const qualifiers = { ...(position.qualifiers || {}) }
                      if (e.target.value) {
                        qualifiers.P580 = [
                          {
                            datavalue: {
                              value: {
                                time: htmlDateToWikidata(e.target.value),
                                precision:
                                  (position.qualifiers?.P580?.[0]?.datavalue?.value
                                    ?.precision as number) ?? 11,
                              },
                            },
                          },
                        ]
                      } else {
                        delete qualifiers.P580
                      }
                      updateProperty(position.id, { qualifiers })
                    }}
                    className="flex-1"
                  />
                  <select
                    value={
                      (position.qualifiers?.P580?.[0]?.datavalue?.value?.precision as number) ?? 11
                    }
                    onChange={(e) => {
                      const qualifiers = { ...(position.qualifiers || {}) }
                      if (qualifiers.P580?.[0]?.datavalue?.value) {
                        qualifiers.P580[0].datavalue.value.precision = Number(e.target.value)
                        updateProperty(position.id, { qualifiers })
                      }
                    }}
                    className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
                  >
                    <option value={11}>Day</option>
                    <option value={10}>Month</option>
                    <option value={9}>Year</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">End Date</label>
                <div className="flex gap-2">
                  <Input
                    type="date"
                    value={
                      position.qualifiers?.P582?.[0]?.datavalue?.value?.time
                        ? wikidataDateToHtml(
                            position.qualifiers.P582[0].datavalue.value.time as string,
                          )
                        : ''
                    }
                    onChange={(e) => {
                      const qualifiers = { ...(position.qualifiers || {}) }
                      if (e.target.value) {
                        qualifiers.P582 = [
                          {
                            datavalue: {
                              value: {
                                time: htmlDateToWikidata(e.target.value),
                                precision:
                                  (position.qualifiers?.P582?.[0]?.datavalue?.value
                                    ?.precision as number) ?? 11,
                              },
                            },
                          },
                        ]
                      } else {
                        delete qualifiers.P582
                      }
                      updateProperty(position.id, { qualifiers })
                    }}
                    className="flex-1"
                  />
                  <select
                    value={
                      (position.qualifiers?.P582?.[0]?.datavalue?.value?.precision as number) ?? 11
                    }
                    onChange={(e) => {
                      const qualifiers = { ...(position.qualifiers || {}) }
                      if (qualifiers.P582?.[0]?.datavalue?.value) {
                        qualifiers.P582[0].datavalue.value.precision = Number(e.target.value)
                        updateProperty(position.id, { qualifiers })
                      }
                    }}
                    className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
                  >
                    <option value={11}>Day</option>
                    <option value={10}>Month</option>
                    <option value={9}>Year</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Birthplaces */}
      <div className="space-y-4">
        <h2 className="text-lg font-medium text-gray-900">Birthplaces</h2>
        <EntitySearch
          searchEndpoint="/api/locations"
          placeholder="Search for birthplaces..."
          onSelect={(result) =>
            addProperty({
              id: crypto.randomUUID(),
              type: PropertyType.P19,
              entity_id: result.wikidata_id,
              entity_name: result.name,
            })
          }
        />
        {birthplaces.map((birthplace) => (
          <div key={birthplace.id} className="p-4 border border-gray-200 rounded-md bg-gray-50">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-medium text-gray-900">{birthplace.entity_name}</div>
                <div className="text-sm text-gray-500">{birthplace.entity_id}</div>
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => removeProperty(birthplace.id)}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Remove
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Citizenships */}
      <div className="space-y-4">
        <h2 className="text-lg font-medium text-gray-900">Citizenships</h2>
        <EntitySearch
          searchEndpoint="/api/countries"
          placeholder="Search for countries..."
          onSelect={(result) =>
            addProperty({
              id: crypto.randomUUID(),
              type: PropertyType.P27,
              entity_id: result.wikidata_id,
              entity_name: result.name,
            })
          }
        />
        {citizenships.map((citizenship) => (
          <div key={citizenship.id} className="p-4 border border-gray-200 rounded-md bg-gray-50">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-medium text-gray-900">{citizenship.entity_name}</div>
                <div className="text-sm text-gray-500">{citizenship.entity_id}</div>
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => removeProperty(citizenship.id)}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Remove
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
