'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { EntitySearch } from '@/components/ui/EntitySearch'
import { SearchEntity } from '@/types'

export function SearchBox() {
  const router = useRouter()

  const onSearch = useCallback(async (query: string): Promise<SearchEntity[]> => {
    const res = await fetch(`/api/politicians/search?q=${encodeURIComponent(query)}`)
    if (!res.ok) throw new Error('Search failed')
    return res.json()
  }, [])

  return (
    <div className="w-96">
      <EntitySearch
        onSearch={onSearch}
        onSelect={(entity) => router.push(`/politician/${entity.wikidata_id}`)}
        placeholder="Search politicians..."
      />
    </div>
  )
}
