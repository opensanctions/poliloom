'use client'

import { useState, useEffect, useRef } from 'react'
import { Property, PropertyType } from '@/types'
import { Input } from './Input'
import { Button } from './Button'
import { Spinner } from './Spinner'

interface AddPropertyFormProps {
  onAddProperty: (property: Property) => void
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
  value: string
  onChange: (value: string) => void
}

function EntitySearch({
  searchEndpoint,
  onSelect,
  placeholder,
  value,
  onChange,
}: EntitySearchProps) {
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

    if (!value.trim()) {
      setSearchResults([])
      setShowDropdown(false)
      setIsSearching(false)
      return
    }

    searchTimeoutRef.current = setTimeout(async () => {
      setIsSearching(true)
      try {
        const response = await fetch(
          `${searchEndpoint}?search=${encodeURIComponent(value)}&limit=10`,
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
  }, [value, searchEndpoint])

  const handleSelect = (result: SearchResult) => {
    onSelect(result)
    setShowDropdown(false)
    setSearchResults([])
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <Input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
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

export function AddPropertyForm({ onAddProperty }: AddPropertyFormProps) {
  const [sourceUrl, setSourceUrl] = useState('')
  const [propertyType, setPropertyType] = useState<PropertyType | ''>('')

  // Date properties (P569, P570)
  const [dateValue, setDateValue] = useState('')
  const [datePrecision, setDatePrecision] = useState(11)

  // Entity-based properties (P39, P19, P27)
  const [entitySearch, setEntitySearch] = useState('')
  const [selectedEntity, setSelectedEntity] = useState<{
    wikidata_id: string
    name: string
  } | null>(null)

  // Position qualifiers (P39 only)
  const [startDate, setStartDate] = useState('')
  const [startDatePrecision, setStartDatePrecision] = useState(11)
  const [endDate, setEndDate] = useState('')
  const [endDatePrecision, setEndDatePrecision] = useState(11)

  // Date conversion helpers
  const htmlDateToWikidata = (htmlDate: string): string => {
    const [year, month, day] = htmlDate.split('-')
    return `+${year}-${month}-${day}T00:00:00Z`
  }

  const buildTimeQualifier = (htmlDate: string, precision: number) => {
    return {
      datatype: 'time',
      snaktype: 'value',
      datavalue: {
        type: 'time',
        value: {
          time: htmlDateToWikidata(htmlDate),
          after: 0,
          before: 0,
          timezone: 0,
          precision: precision,
          calendarmodel: 'http://www.wikidata.org/entity/Q1985727',
        },
      },
    }
  }

  const resetForm = () => {
    setSourceUrl('')
    setPropertyType('')
    setDateValue('')
    setDatePrecision(11)
    setEntitySearch('')
    setSelectedEntity(null)
    setStartDate('')
    setStartDatePrecision(11)
    setEndDate('')
    setEndDatePrecision(11)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!propertyType || !sourceUrl) return

    let property: Property

    // Build references array with source URL
    const references = [
      {
        P854: [
          {
            datatype: 'url',
            property: 'P854',
            snaktype: 'value',
            datavalue: {
              type: 'string',
              value: sourceUrl,
            },
          },
        ],
      },
    ]

    // Date properties (birth/death date)
    if (propertyType === PropertyType.P569 || propertyType === PropertyType.P570) {
      if (!dateValue) return

      property = {
        id: crypto.randomUUID(),
        type: propertyType,
        value: htmlDateToWikidata(dateValue),
        value_precision: datePrecision,
        references,
      }
    }
    // Entity-based properties (positions, birthplaces, citizenships)
    else if (
      propertyType === PropertyType.P39 ||
      propertyType === PropertyType.P19 ||
      propertyType === PropertyType.P27
    ) {
      if (!selectedEntity) return

      property = {
        id: crypto.randomUUID(),
        type: propertyType,
        entity_id: selectedEntity.wikidata_id,
        entity_name: selectedEntity.name,
        references,
      }

      // Add qualifiers for positions
      if (propertyType === PropertyType.P39) {
        const qualifiers: Property['qualifiers'] = {}

        if (startDate) {
          qualifiers.P580 = [buildTimeQualifier(startDate, startDatePrecision)]
        }

        if (endDate) {
          qualifiers.P582 = [buildTimeQualifier(endDate, endDatePrecision)]
        }

        if (Object.keys(qualifiers).length > 0) {
          property.qualifiers = qualifiers
        }
      }
    } else {
      return
    }

    onAddProperty(property)
    resetForm()
  }

  const getEntitySearchEndpoint = () => {
    switch (propertyType) {
      case PropertyType.P39:
        return '/api/positions'
      case PropertyType.P19:
        return '/api/locations'
      case PropertyType.P27:
        return '/api/countries'
      default:
        return ''
    }
  }

  const getEntitySearchPlaceholder = () => {
    switch (propertyType) {
      case PropertyType.P39:
        return 'Search for positions...'
      case PropertyType.P19:
        return 'Search for birthplaces...'
      case PropertyType.P27:
        return 'Search for countries...'
      default:
        return ''
    }
  }

  const isFormValid = () => {
    if (!propertyType || !sourceUrl) return false

    if (propertyType === PropertyType.P569 || propertyType === PropertyType.P570) {
      return dateValue !== ''
    }

    if (
      propertyType === PropertyType.P39 ||
      propertyType === PropertyType.P19 ||
      propertyType === PropertyType.P27
    ) {
      return selectedEntity !== null
    }

    return false
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 p-4 border border-gray-300 rounded-md bg-gray-50"
    >
      <h3 className="text-md font-medium text-gray-900">Add Property</h3>

      {/* Source URL */}
      <div>
        <label htmlFor="sourceUrl" className="block text-sm font-medium text-gray-700 mb-1">
          Source URL <span className="text-red-500">*</span>
        </label>
        <Input
          id="sourceUrl"
          type="url"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          placeholder="https://example.com/politician-page"
          required
        />
        <p className="mt-1 text-xs text-gray-500">
          This URL will be used as a reference for all properties you add
        </p>
      </div>

      {/* Property Type Selector */}
      <div>
        <label htmlFor="propertyType" className="block text-sm font-medium text-gray-700 mb-1">
          Property Type
        </label>
        <select
          id="propertyType"
          value={propertyType}
          onChange={(e) => {
            setPropertyType(e.target.value as PropertyType)
            // Reset form fields when type changes
            setDateValue('')
            setEntitySearch('')
            setSelectedEntity(null)
            setStartDate('')
            setEndDate('')
          }}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
          required
        >
          <option value="">Select a property type...</option>
          <option value={PropertyType.P569}>Birth Date (P569)</option>
          <option value={PropertyType.P570}>Death Date (P570)</option>
          <option value={PropertyType.P39}>Position Held (P39)</option>
          <option value={PropertyType.P19}>Place of Birth (P19)</option>
          <option value={PropertyType.P27}>Country of Citizenship (P27)</option>
        </select>
      </div>

      {/* Date input for birth/death dates */}
      {(propertyType === PropertyType.P569 || propertyType === PropertyType.P570) && (
        <div>
          <label htmlFor="dateValue" className="block text-sm font-medium text-gray-700 mb-1">
            Date
          </label>
          <div className="flex gap-2">
            <Input
              id="dateValue"
              type="date"
              value={dateValue}
              onChange={(e) => setDateValue(e.target.value)}
              className="flex-1"
              required
            />
            <select
              value={datePrecision}
              onChange={(e) => setDatePrecision(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
            >
              <option value={11}>Day</option>
              <option value={10}>Month</option>
              <option value={9}>Year</option>
            </select>
          </div>
        </div>
      )}

      {/* Entity search for entity-based properties */}
      {(propertyType === PropertyType.P39 ||
        propertyType === PropertyType.P19 ||
        propertyType === PropertyType.P27) && (
        <div>
          <label htmlFor="entitySearch" className="block text-sm font-medium text-gray-700 mb-1">
            {propertyType === PropertyType.P39 && 'Position'}
            {propertyType === PropertyType.P19 && 'Birthplace'}
            {propertyType === PropertyType.P27 && 'Country'}
          </label>
          {selectedEntity ? (
            <div className="p-3 bg-white border border-gray-300 rounded-md flex justify-between items-center">
              <div>
                <div className="font-medium text-gray-900">{selectedEntity.name}</div>
                <div className="text-sm text-gray-500">{selectedEntity.wikidata_id}</div>
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setSelectedEntity(null)
                  setEntitySearch('')
                }}
                className="text-sm"
              >
                Clear
              </Button>
            </div>
          ) : (
            <EntitySearch
              searchEndpoint={getEntitySearchEndpoint()}
              placeholder={getEntitySearchPlaceholder()}
              value={entitySearch}
              onChange={setEntitySearch}
              onSelect={(result) => {
                setSelectedEntity({
                  wikidata_id: result.wikidata_id,
                  name: result.name,
                })
                setEntitySearch('')
              }}
            />
          )}
        </div>
      )}

      {/* Date qualifiers for positions */}
      {propertyType === PropertyType.P39 && selectedEntity && (
        <div className="space-y-3 pt-3 border-t border-gray-300">
          <h4 className="text-sm font-medium text-gray-700">Position Dates (Optional)</h4>

          {/* Start Date */}
          <div>
            <label htmlFor="startDate" className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <div className="flex gap-2">
              <Input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="flex-1"
              />
              <select
                value={startDatePrecision}
                onChange={(e) => setStartDatePrecision(Number(e.target.value))}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
                disabled={!startDate}
              >
                <option value={11}>Day</option>
                <option value={10}>Month</option>
                <option value={9}>Year</option>
              </select>
            </div>
          </div>

          {/* End Date */}
          <div>
            <label htmlFor="endDate" className="block text-sm font-medium text-gray-700 mb-1">
              End Date
            </label>
            <div className="flex gap-2">
              <Input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="flex-1"
              />
              <select
                value={endDatePrecision}
                onChange={(e) => setEndDatePrecision(Number(e.target.value))}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
                disabled={!endDate}
              >
                <option value={11}>Day</option>
                <option value={10}>Month</option>
                <option value={9}>Year</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={!isFormValid()} className="flex-1">
          Add Property
        </Button>
        {propertyType && (
          <Button type="button" variant="secondary" onClick={resetForm}>
            Clear
          </Button>
        )}
      </div>
    </form>
  )
}
