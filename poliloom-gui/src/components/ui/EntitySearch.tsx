'use client'

import { useRef, useEffect } from 'react'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useEntitySearch } from '@/hooks/useEntitySearch'

export interface EntitySearchProps {
  searchEndpoint: string
  onSelect: (entity: { wikidata_id: string; name: string }) => void
  onClear: () => void
  selectedEntity: { wikidata_id: string; name: string } | null
  placeholder?: string
  disabled?: boolean
}

export function EntitySearch({
  searchEndpoint,
  onSelect,
  onClear,
  selectedEntity,
  placeholder = 'Search...',
  disabled = false,
}: EntitySearchProps) {
  const { query, setQuery, results, isLoading, isOpen, setIsOpen, clear } =
    useEntitySearch(searchEndpoint)
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
  }, [setIsOpen])

  if (selectedEntity) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-foreground">
          {selectedEntity.name}{' '}
          <span className="text-foreground-muted text-sm">({selectedEntity.wikidata_id})</span>
        </span>
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className="text-foreground-muted hover:text-foreground text-sm"
        >
          Clear
        </button>
      </div>
    )
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
                clear()
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
