'use client'

import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { SearchEntity, SearchFn } from '@/types'
import { best_label } from '@/lib/labels'

function entityName(entity: SearchEntity): string {
  return best_label(entity.terms, [], entity.wikidata_id)
}

function entityDescription(entity: SearchEntity): string | undefined {
  return entity.terms.descriptions.en ?? Object.values(entity.terms.descriptions)[0]
}

class SelectItem {
  constructor(public entity: SearchEntity) {}
}

export interface EntitySearchProps {
  onSearch: SearchFn
  onSelect: (entity: { wikidata_id: string; name: string }) => void
  placeholder?: string
  disabled?: boolean
}

export function EntitySearch({
  onSearch,
  onSelect,
  placeholder = 'Search...',
  disabled = false,
}: EntitySearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchEntity[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (query.length === 0) return

    let cancelled = false

    async function search() {
      setIsLoading(true)
      try {
        const data = await onSearch(query)
        if (!cancelled) {
          setResults(data)
          setIsOpen(true)
        }
      } catch {
        if (!cancelled) {
          setResults([])
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
          setActiveIndex(-1)
        }
      }
    }

    search()

    return () => {
      cancelled = true
    }
  }, [query, onSearch])

  const items: SelectItem[] = results.map((entity) => new SelectItem(entity))

  useEffect(() => {
    if (activeIndex >= 0) {
      const el = document.getElementById(`entity-option-${activeIndex}`)
      el?.scrollIntoView({ block: 'nearest' })
    }
  }, [activeIndex])

  function resetDropdown() {
    setResults([])
    setIsOpen(false)
    setIsLoading(false)
    setActiveIndex(-1)
  }

  function handleQueryChange(value: string) {
    setQuery(value)
    if (value.length === 0) resetDropdown()
  }

  function selectItem(item: SelectItem) {
    onSelect({ wikidata_id: item.entity.wikidata_id, name: entityName(item.entity) })
    setQuery('')
    resetDropdown()
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || items.length === 0) {
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex((prev) => (prev + 1) % items.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex((prev) => (prev <= 0 ? items.length - 1 : prev - 1))
        break
      case 'Enter':
        e.preventDefault()
        if (activeIndex >= 0) {
          selectItem(items[activeIndex])
        }
        break
      case 'Escape':
        e.preventDefault()
        setIsOpen(false)
        setActiveIndex(-1)
        break
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          role="combobox"
          aria-expanded={isOpen}
          aria-activedescendant={activeIndex >= 0 ? `entity-option-${activeIndex}` : undefined}
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Spinner />
          </div>
        )}
      </div>

      {isOpen && items.length > 0 && (
        <ul
          ref={listRef}
          role="listbox"
          className="absolute z-10 mt-1 w-full bg-surface border border-border-strong rounded-md shadow-lg max-h-60 overflow-auto"
        >
          {items.map((item, i) => (
            <li
              key={item.entity.wikidata_id}
              id={`entity-option-${i}`}
              role="option"
              aria-selected={activeIndex === i}
              onClick={() => selectItem(item)}
              onMouseMove={() => setActiveIndex(i)}
              className={`px-3 py-2 cursor-pointer ${activeIndex === i ? 'bg-accent-muted' : ''}`}
            >
              <div className="text-foreground">{entityName(item.entity)}</div>
              <div className="text-foreground-muted text-sm">
                {entityDescription(item.entity) && <span>{entityDescription(item.entity)} · </span>}
                {item.entity.wikidata_id}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
