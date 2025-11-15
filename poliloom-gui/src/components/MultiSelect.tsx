'use client'

import { useState } from 'react'
import { ContainerBox } from './ContainerBox'

export interface MultiSelectOption {
  value: string
  label: string
  count?: number
}

interface MultiSelectProps {
  options: MultiSelectOption[]
  selected: string[]
  onChange: (selected: string[]) => void
  title: string
  description: string
  icon?: string
  loading?: boolean
  disabled?: boolean
}

export function MultiSelect({
  options,
  selected,
  onChange,
  title,
  description,
  icon,
  loading = false,
  disabled = false,
}: MultiSelectProps) {
  const [searchTerm, setSearchTerm] = useState('')

  // Normalize text for searching (removes diacritics)
  const normalizeText = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()

  // Filter options based on search term
  const filteredOptions = options.filter((option) => {
    if (!searchTerm) return false // Only show results when searching
    const label = option.label.toLowerCase()
    const search = searchTerm.toLowerCase()
    const normalizedLabel = normalizeText(option.label)
    const normalizedSearch = normalizeText(searchTerm)
    return label.includes(search) || normalizedLabel.includes(normalizedSearch)
  })

  // Sort filtered results by count (highest first), then alphabetically
  const sortedFilteredOptions = filteredOptions.sort((a, b) => {
    if (a.count !== undefined && b.count !== undefined && a.count !== b.count) {
      return b.count - a.count
    }
    return a.label.localeCompare(b.label)
  })

  // Get selected options
  const selectedOptions = options.filter((opt) => selected.includes(opt.value))

  // Calculate how many popular items we need to reach 6 total
  const targetTotal = 6
  const remainingSlots = Math.max(0, targetTotal - selectedOptions.length)

  // Get top suggestions by count when not searching
  const topSuggestions = options
    .filter((opt) => opt.count && opt.count > 0 && !selected.includes(opt.value))
    .sort((a, b) => (b.count || 0) - (a.count || 0))
    .slice(0, remainingSlots)

  // Show suggestions or search results, always including selected items
  const displayOptions = searchTerm
    ? sortedFilteredOptions
    : [...selectedOptions, ...topSuggestions]

  const toggleOption = (value: string) => {
    if (disabled) return
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value))
    } else {
      onChange([...selected, value])
    }
    setSearchTerm('')
  }

  return (
    <ContainerBox title={title} description={description} icon={icon} loading={loading}>
      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Start typing to search..."
          disabled={disabled || loading}
          className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-50 disabled:cursor-not-allowed text-sm text-gray-900 placeholder-gray-400 transition-all"
          autoComplete="off"
        />
      </div>

      {/* Options as chips */}
      {displayOptions.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {displayOptions.map((option) => {
            const isSelected = selected.includes(option.value)
            return (
              <button
                key={option.value}
                onClick={() => toggleOption(option.value)}
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                disabled={disabled || loading}
                className={`
                    px-4 py-2 rounded-lg text-sm font-medium transition-all
                    border-2 disabled:cursor-not-allowed inline-flex items-center gap-2
                    ${
                      isSelected
                        ? 'bg-indigo-600 border-indigo-600 text-white hover:bg-indigo-700 hover:border-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-700 hover:border-indigo-300 hover:bg-indigo-50'
                    }
                    ${disabled ? 'opacity-50' : ''}
                  `}
              >
                <span>{option.label}</span>
                {option.count !== undefined && option.count > 0 && (
                  <span
                    className={`text-xs font-semibold ${isSelected ? 'text-indigo-200' : 'text-gray-500'}`}
                  >
                    {option.count.toLocaleString()}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="text-sm text-gray-500 text-center py-4">
          {searchTerm ? 'No matching options found' : 'Start typing to search'}
        </div>
      )}
    </ContainerBox>
  )
}
