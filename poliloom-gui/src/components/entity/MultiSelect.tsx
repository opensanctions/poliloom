'use client'

import { useState } from 'react'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'

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
    <HeaderedBox title={title} description={description} icon={icon}>
      {/* Search */}
      <div className="mb-4">
        <Input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Start typing to search..."
          disabled={disabled || loading}
          autoComplete="off"
        />
      </div>

      {/* Options as chips */}
      {loading ? (
        <div className="flex justify-center py-2">
          <Spinner />
        </div>
      ) : displayOptions.length > 0 ? (
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
                disabled={disabled}
                className={`
                    px-4 py-2 rounded-md text-sm font-medium transition-all cursor-pointer
                    border disabled:cursor-not-allowed inline-flex items-center gap-2
                    ${
                      isSelected
                        ? 'bg-accent border-accent text-accent-on-solid hover:bg-accent-hover hover:border-accent-hover'
                        : 'bg-surface border-border-strong text-foreground-secondary hover:border-accent-border-hover hover:bg-accent-muted'
                    }
                    ${disabled ? 'opacity-50' : ''}
                  `}
              >
                <span>{option.label}</span>
                {option.count !== undefined && option.count > 0 && (
                  <span
                    className={`text-xs font-semibold ${isSelected ? 'text-accent-on-solid-muted' : 'text-foreground-muted'}`}
                  >
                    {option.count.toLocaleString()}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="text-sm text-foreground-muted text-center py-4">
          {searchTerm ? 'No matching options found' : 'Start typing to search'}
        </div>
      )}
    </HeaderedBox>
  )
}
