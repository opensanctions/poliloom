'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { EntitySearch } from '@/components/ui/EntitySearch'
import { CreatePoliticianResponse } from '@/types'

export function OmniBox() {
  const router = useRouter()
  const [isCreating, setIsCreating] = useState(false)

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
        searchEndpoint="/api/politicians/search"
        onSelect={(entity) => router.push(`/politician/${entity.wikidata_id}`)}
        onCreate={handleCreate}
        placeholder="Search politicians..."
        disabled={isCreating}
      />
    </div>
  )
}
