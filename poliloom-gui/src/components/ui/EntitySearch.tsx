'use client'

import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'

interface Entity {
  wikidata_id: string
  name: string
  description?: string
}

export interface EntitySearchProps {
  searchEndpoint: string
  onSelect: (entity: { wikidata_id: string; name: string }) => void
  placeholder?: string
  disabled?: boolean
}

export function EntitySearch({
  searchEndpoint,
  onSelect,
  placeholder = 'Search...',
  disabled = false,
}: EntitySearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Entity[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

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

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={disabled}
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Spinner />
          </div>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 w-full bg-surface border border-border-strong rounded-md shadow-lg max-h-60 overflow-auto"
        >
          {results.map((entity) => (
            <li
              key={entity.wikidata_id}
              role="option"
              aria-selected={false}
              onClick={() => {
                onSelect({ wikidata_id: entity.wikidata_id, name: entity.name })
                setQuery('')
                setResults([])
                setIsOpen(false)
              }}
              className="px-3 py-2 cursor-pointer hover:bg-accent-muted"
            >
              <div className="text-foreground">{entity.name}</div>
              <div className="text-foreground-muted text-sm">
                {entity.description && <span>{entity.description} · </span>}
                {entity.wikidata_id}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
