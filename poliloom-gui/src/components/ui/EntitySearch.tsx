'use client'

import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'

interface Entity {
  wikidata_id: string
  name: string
  description?: string
}

class CreateItem {
  constructor(public name: string) {}
}

class SelectItem {
  constructor(public entity: Entity) {}
}

type DropdownItem = CreateItem | SelectItem

export interface EntitySearchProps {
  searchEndpoint: string
  onSelect: (entity: { wikidata_id: string; name: string }) => void
  onCreate?: (name: string) => void
  placeholder?: string
  disabled?: boolean
}

export function EntitySearch({
  searchEndpoint,
  onSelect,
  onCreate,
  placeholder = 'Search...',
  disabled = false,
}: EntitySearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Entity[]>([])
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
    if (query.length === 0) {
      setResults([])
      setIsOpen(false)
      return
    }

    let cancelled = false

    async function search() {
      setIsLoading(true)
      try {
        const res = await fetch(`${searchEndpoint}?q=${encodeURIComponent(query)}`)
        if (!res.ok) throw new Error('Search failed')
        const data = await res.json()
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
        }
      }
    }

    search()

    return () => {
      cancelled = true
    }
  }, [query, searchEndpoint])

  const items: DropdownItem[] = [
    ...(onCreate && query.trim() ? [new CreateItem(query.trim())] : []),
    ...results.map((entity) => new SelectItem(entity)),
  ]

  useEffect(() => {
    setActiveIndex(-1)
  }, [results])

  useEffect(() => {
    if (activeIndex >= 0) {
      const el = document.getElementById(`entity-option-${activeIndex}`)
      el?.scrollIntoView({ block: 'nearest' })
    }
  }, [activeIndex])

  function selectItem(item: DropdownItem) {
    if (item instanceof SelectItem) {
      onSelect({ wikidata_id: item.entity.wikidata_id, name: item.entity.name })
    } else {
      onCreate!(item.name)
    }
    setQuery('')
    setResults([])
    setIsOpen(false)
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
          onChange={(e) => setQuery(e.target.value)}
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
              key={item instanceof CreateItem ? '__create__' : item.entity.wikidata_id}
              id={`entity-option-${i}`}
              role="option"
              aria-selected={activeIndex === i}
              onClick={() => selectItem(item)}
              onMouseMove={() => setActiveIndex(i)}
              className={`px-3 py-2 cursor-pointer ${item instanceof CreateItem ? 'border-b border-border' : ''} ${activeIndex === i ? 'bg-accent-muted' : ''}`}
            >
              {item instanceof CreateItem ? (
                <div className="text-foreground">
                  Create <strong>&ldquo;{item.name}&rdquo;</strong> in Wikidata
                </div>
              ) : (
                <>
                  <div className="text-foreground">{item.entity.name}</div>
                  <div className="text-foreground-muted text-sm">
                    {item.entity.description && <span>{item.entity.description} · </span>}
                    {item.entity.wikidata_id}
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
