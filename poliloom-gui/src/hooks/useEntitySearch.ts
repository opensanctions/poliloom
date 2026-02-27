import { useState, useEffect } from 'react'

interface Entity {
  wikidata_id: string
  name: string
  description?: string
}

export function useEntitySearch(searchEndpoint: string) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Entity[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

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

  function clear() {
    setQuery('')
    setResults([])
    setIsOpen(false)
  }

  return { query, setQuery, results, isLoading, isOpen, setIsOpen, clear }
}
