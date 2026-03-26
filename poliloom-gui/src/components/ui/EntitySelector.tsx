'use client'

import { EntitySearch } from '@/components/ui/EntitySearch'
import { SearchFn } from '@/types'

export interface EntitySelectorProps {
  onSearch: SearchFn
  onSelect: (entity: { wikidata_id: string; name: string }) => void
  onClear: () => void
  selectedEntity: { wikidata_id: string; name: string } | null
  placeholder?: string
  disabled?: boolean
}

export function EntitySelector({
  onSearch,
  onSelect,
  onClear,
  selectedEntity,
  placeholder,
  disabled = false,
}: EntitySelectorProps) {
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
    <EntitySearch
      onSearch={onSearch}
      onSelect={onSelect}
      placeholder={placeholder}
      disabled={disabled}
    />
  )
}
