'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { EntitySearch } from '@/components/ui/EntitySearch'
import { CreatePoliticianResponse, SearchEntity } from '@/types'

export function OmniBox() {
  const router = useRouter()
  const [isCreating, setIsCreating] = useState(false)

  const onSearch = useCallback(async (query: string): Promise<SearchEntity[]> => {
    const res = await fetch(`/api/politicians/search?q=${encodeURIComponent(query)}`)
    if (!res.ok) throw new Error('Search failed')
    return res.json()
  }, [])

  const handleCreate = async (name: string) => {
    setIsCreating(true)
    try {
      const response = await fetch('/api/politicians', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })

      if (!response.ok) {
        throw new Error(`Failed to create politician: ${response.statusText}`)
      }

      const result: CreatePoliticianResponse = await response.json()
      if (result.success && result.wikidata_id) {
        router.push(`/politician/${result.wikidata_id}`)
      }
    } catch (error) {
      console.error('Failed to create politician:', error)
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="w-96">
      <EntitySearch
        onSearch={onSearch}
        onSelect={(entity) => router.push(`/politician/${entity.wikidata_id}`)}
        onCreate={handleCreate}
        placeholder="Search politicians..."
        disabled={isCreating}
      />
    </div>
  )
}
