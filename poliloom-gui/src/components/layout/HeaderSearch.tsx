'use client'

import { useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useEntitySearch } from '@/hooks/useEntitySearch'
import { Spinner } from '@/components/ui/Spinner'

export function HeaderSearch() {
  const router = useRouter()
  const { query, setQuery, results, isLoading, isOpen, setIsOpen, clear } =
    useEntitySearch('/api/politicians/search')
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [setIsOpen])

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [setIsOpen])

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <svg
          className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted pointer-events-none"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
          />
        </svg>
        <input
          type="text"
          placeholder="Search politicians..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-56 h-8 pl-8 pr-8 text-sm rounded-md border border-border bg-background text-foreground placeholder:text-foreground-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
        />
        {isLoading && (
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
            <Spinner />
          </div>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-50 mt-1 w-72 bg-surface border border-border-strong rounded-md shadow-lg max-h-80 overflow-auto"
        >
          {results.map((entity) => (
            <li
              key={entity.wikidata_id}
              role="option"
              aria-selected={false}
              onClick={() => {
                router.push(`/politician/${entity.wikidata_id}`)
                clear()
              }}
              className="px-3 py-2 cursor-pointer hover:bg-accent-muted"
            >
              <div className="text-foreground text-sm">{entity.name}</div>
              <div className="text-foreground-muted text-xs">
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
