'use client'

import { useRouter } from 'next/navigation'
import { EntitySearch } from '@/components/ui/EntitySearch'

export function OmniBox() {
  const router = useRouter()

  return (
    <div className="w-96">
      <EntitySearch
        searchEndpoint="/api/politicians/search"
        onSelect={(entity) => router.push(`/politician/${entity.wikidata_id}`)}
        placeholder="Search politicians..."
      />
    </div>
  )
}
