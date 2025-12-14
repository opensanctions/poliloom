'use client'

import { useState, useRef, useEffect } from 'react'

export interface SelectOption {
  value: string
  label: string
}

interface SelectProps {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  label?: string
  required?: boolean
  error?: string
  disabled?: boolean
  className?: string
}

export function Select({
  options,
  value,
  onChange,
  label,
  required,
  error,
  disabled = false,
  className = '',
}: SelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selectedOption = options.find((opt) => opt.value === value)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const baseClasses =
    'w-full px-3 py-2 pr-4 border border-border-strong rounded-md focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent text-foreground bg-surface text-left flex items-center justify-between gap-3'

  const errorClasses = error ? 'border-danger-subtle focus:ring-danger-subtle' : ''
  const disabledClasses = disabled
    ? 'bg-surface-hover text-foreground-muted cursor-not-allowed opacity-60'
    : ''

  return (
    <div className={className} ref={containerRef}>
      {label && (
        <label className="block text-sm font-medium text-foreground-secondary mb-2">
          {label}
          {required && <span className="text-danger-subtle"> *</span>}
        </label>
      )}
      <div className="relative">
        <button
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          className={`${baseClasses} ${errorClasses} ${disabledClasses}`}
        >
          <span className="grid">
            {options.map((opt) => (
              <span
                key={opt.value}
                className={`col-start-1 row-start-1 ${opt.value === value ? 'visible' : 'invisible'}`}
              >
                {opt.label}
              </span>
            ))}
          </span>
          <svg
            className={`w-4 h-4 text-foreground-subtle transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isOpen && (
          <div className="absolute z-10 mt-1 w-full bg-surface border border-border-strong rounded-md shadow-lg max-h-60 overflow-auto">
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value)
                  setIsOpen(false)
                }}
                className={`w-full px-3 py-2 text-left text-foreground hover:bg-accent-muted ${
                  option.value === value ? 'bg-accent-muted font-medium' : ''
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
      {error && <p className="mt-1 text-sm text-danger-foreground">{error}</p>}
    </div>
  )
}
