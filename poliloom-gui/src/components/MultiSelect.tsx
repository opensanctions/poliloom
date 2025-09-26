"use client"

import { useState, useRef, useEffect } from 'react'

export interface MultiSelectOption {
  value: string
  label: string
}

interface MultiSelectProps {
  options: MultiSelectOption[]
  selected: string[]
  onChange: (selected: string[]) => void
  placeholder?: string
  loading?: boolean
  disabled?: boolean
  className?: string
}

export function MultiSelect({
  options,
  selected,
  onChange,
  placeholder = "Select options...",
  loading = false,
  disabled = false,
  className = ""
}: MultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSearchTerm("")
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Filter and sort options based on search term
  const filteredOptions = options
    .filter(option =>
      option.label.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => a.label.localeCompare(b.label))

  const selectedOptions = options.filter(option => selected.includes(option.value))

  const toggleOption = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter(v => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  const removeOption = (value: string) => {
    onChange(selected.filter(v => v !== value))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false)
      setSearchTerm("")
    }
  }

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Input field with selected items */}
      <div
        className={`min-h-[42px] px-3 py-2 border border-gray-300 rounded-md bg-white focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-indigo-500 ${
          disabled ? 'bg-gray-50' : ''
        }`}
      >
        <div className="flex flex-wrap gap-1 items-center">
          {selectedOptions.map(option => (
            <span
              key={option.value}
              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-indigo-100 text-indigo-800"
            >
              {option.label}
              {!disabled && (
                <button
                  type="button"
                  className="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-indigo-200 focus:outline-none focus:bg-indigo-200 text-indigo-600 font-bold text-xs leading-none"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeOption(option.value)
                  }}
                >
                  ×
                </button>
              )}
            </span>
          ))}

          <div className="flex-1 min-w-[120px] relative">
            <input
              ref={inputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsOpen(true)}
              className="w-full border-none outline-none text-sm bg-transparent text-gray-900 placeholder-gray-400"
              placeholder={selectedOptions.length === 0 ? placeholder : "Search..."}
              disabled={disabled || loading}
            />
          </div>

          <div className="flex items-center">
            {loading && (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-indigo-600 mr-2"></div>
            )}
            <button
              type="button"
              onClick={() => setIsOpen(!isOpen)}
              disabled={disabled || loading}
              className="text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed"
            >
              <span
                className={`transition-transform text-sm ${
                  isOpen ? 'transform rotate-180' : ''
                }`}
              >
                ▼
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Dropdown */}
      {isOpen && !disabled && !loading && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
          {filteredOptions.length === 0 ? (
            <div className="px-3 py-2 text-sm text-gray-500">
              {searchTerm ? 'No matching options' : 'No options available'}
            </div>
          ) : (
            filteredOptions.map(option => {
              const isSelected = selected.includes(option.value)
              return (
                <div
                  key={option.value}
                  className={`px-3 py-2 cursor-pointer text-sm hover:bg-gray-50 ${
                    isSelected ? 'bg-indigo-50 text-indigo-700' : 'text-gray-900'
                  }`}
                  onClick={() => toggleOption(option.value)}
                >
                  <div className="flex items-center justify-between">
                    <span>{option.label}</span>
                    {isSelected && (
                      <span className="text-indigo-600">✓</span>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}