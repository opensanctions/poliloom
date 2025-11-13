'use client'

import { useState } from 'react'
import { Spinner } from './Spinner'

export interface MultiSelectOption {
  value: string
  label: string
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
  const [isExpanded, setIsExpanded] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  // Normalize text for searching (removes diacritics)
  const normalizeText = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()

  // Filter and sort options
  const filteredOptions = options
    .filter((option) => {
      if (!searchTerm) return true
      const label = option.label.toLowerCase()
      const search = searchTerm.toLowerCase()
      const normalizedLabel = normalizeText(option.label)
      const normalizedSearch = normalizeText(searchTerm)
      return label.includes(search) || normalizedLabel.includes(normalizedSearch)
    })
    .sort((a, b) => a.label.localeCompare(b.label))

  // Show top 8 popular options when collapsed
  const displayOptions = isExpanded ? filteredOptions : filteredOptions.slice(0, 8)

  const toggleOption = (value: string) => {
    if (disabled) return
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  const clearAll = () => {
    if (!disabled) {
      onChange([])
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden transition-all hover:shadow-md">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {icon && <span className="text-2xl">{icon}</span>}
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
              <p className="text-sm text-gray-600 mt-0.5">{description}</p>
            </div>
          </div>
          {loading && (
            <div className="ml-4">
              <Spinner />
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-5">
        {/* Selected count and clear */}
        {selected.length > 0 && (
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
            <span className="text-sm font-medium text-indigo-700">{selected.length} selected</span>
            <button
              onClick={clearAll}
              disabled={disabled}
              className="text-sm text-gray-600 hover:text-gray-900 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              Clear all
            </button>
          </div>
        )}

        {/* Search */}
        {isExpanded && (
          <div className="mb-4">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search..."
              disabled={disabled || loading}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-50 disabled:cursor-not-allowed text-sm"
            />
          </div>
        )}

        {/* Options as chips */}
        {displayOptions.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {displayOptions.map((option) => {
              const isSelected = selected.includes(option.value)
              return (
                <button
                  key={option.value}
                  onClick={() => toggleOption(option.value)}
                  disabled={disabled || loading}
                  className={`
                    px-4 py-2 rounded-lg text-sm font-medium transition-all
                    border-2 disabled:cursor-not-allowed
                    ${
                      isSelected
                        ? 'bg-indigo-600 border-indigo-600 text-white hover:bg-indigo-700 hover:border-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-700 hover:border-indigo-300 hover:bg-indigo-50'
                    }
                    ${disabled ? 'opacity-50' : ''}
                  `}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        ) : (
          <div className="text-sm text-gray-500 text-center py-4">
            {searchTerm ? 'No matching options' : 'No options available'}
          </div>
        )}

        {/* Expand/collapse button */}
        {filteredOptions.length > 8 && (
          <div className="mt-4 text-center">
            <button
              onClick={() => {
                setIsExpanded(!isExpanded)
                if (isExpanded) setSearchTerm('')
              }}
              disabled={disabled || loading}
              className="text-sm font-medium text-indigo-600 hover:text-indigo-800 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-1"
            >
              {isExpanded ? (
                <>
                  Show less
                  <span className="text-xs">▲</span>
                </>
              ) : (
                <>
                  Show all {filteredOptions.length} options
                  <span className="text-xs">▼</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
