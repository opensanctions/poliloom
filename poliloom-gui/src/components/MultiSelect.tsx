'use client'

import { useState, useRef, useEffect } from 'react'
import { Spinner } from './Spinner'

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
  placeholder = 'Select options...',
  loading = false,
  disabled = false,
  className = '',
}: MultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSearchTerm('')
        setFocusedIndex(-1)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Normalize text for searching (removes diacritics)
  const normalizeText = (text: string) =>
    text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()

  // Filter and sort options based on search term
  const filteredOptions = options
    .filter((option) => {
      const label = option.label.toLowerCase()
      const search = searchTerm.toLowerCase()
      const normalizedLabel = normalizeText(option.label)
      const normalizedSearch = normalizeText(searchTerm)

      // Match either the original text or normalized text
      return label.includes(search) || normalizedLabel.includes(normalizedSearch)
    })
    .sort((a, b) => a.label.localeCompare(b.label))

  // Reset focused index when filtered options change
  useEffect(() => {
    setFocusedIndex(-1)
  }, [filteredOptions.length, searchTerm])

  const selectedOptions = options.filter((option) => selected.includes(option.value))

  const toggleOption = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  const removeOption = (value: string) => {
    onChange(selected.filter((v) => v !== value))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        setIsOpen(true)
        setFocusedIndex(0)
      }
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setFocusedIndex((prev) => (prev < filteredOptions.length - 1 ? prev + 1 : 0))
        break
      case 'ArrowUp':
        e.preventDefault()
        setFocusedIndex((prev) => (prev > 0 ? prev - 1 : filteredOptions.length - 1))
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (focusedIndex >= 0 && focusedIndex < filteredOptions.length) {
          toggleOption(filteredOptions[focusedIndex].value)
          setSearchTerm('')
        }
        break
      case 'Tab':
        setIsOpen(false)
        setSearchTerm('')
        setFocusedIndex(-1)
        break
    }
  }

  const handleBlur = (e: React.FocusEvent) => {
    // Check if the new focus target is within our dropdown
    if (dropdownRef.current && !dropdownRef.current.contains(e.relatedTarget as Node)) {
      setIsOpen(false)
      setSearchTerm('')
      setFocusedIndex(-1)
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
          {selectedOptions.map((option) => (
            <span
              key={option.value}
              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-700"
            >
              {option.label}
              {!disabled && (
                <button
                  type="button"
                  className="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-blue-200 focus:outline-none focus:bg-blue-200 text-blue-600 font-bold text-xs leading-none"
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
              onFocus={() => {
                setIsOpen(true)
                setFocusedIndex(-1)
              }}
              onBlur={handleBlur}
              className="w-full border-none outline-none text-sm bg-transparent text-gray-900 placeholder-gray-400"
              placeholder={selectedOptions.length === 0 ? placeholder : 'Search...'}
              disabled={disabled || loading}
            />
          </div>

          <div className="flex items-center">
            {loading && <Spinner />}
            <button
              type="button"
              onClick={() => {
                setIsOpen(!isOpen)
                setFocusedIndex(-1)
              }}
              disabled={disabled || loading}
              className="text-gray-400 hover:text-gray-600 disabled:cursor-not-allowed"
            >
              <span
                className={`transition-transform text-sm ${isOpen ? 'transform rotate-180' : ''}`}
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
            filteredOptions.map((option, index) => {
              const isSelected = selected.includes(option.value)
              const isFocused = index === focusedIndex
              return (
                <div
                  key={option.value}
                  className={`px-3 py-2 cursor-pointer text-sm hover:bg-gray-50 ${
                    isSelected ? 'bg-indigo-50 text-indigo-700' : 'text-gray-900'
                  } ${isFocused ? 'ring-2 ring-indigo-500 ring-inset bg-indigo-50' : ''}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => toggleOption(option.value)}
                  onMouseEnter={() => setFocusedIndex(index)}
                >
                  <div className="flex items-center justify-between">
                    <span>{option.label}</span>
                    {isSelected && <span className="text-indigo-600">✓</span>}
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
