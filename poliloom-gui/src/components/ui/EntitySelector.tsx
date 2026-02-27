'use client'

import { EntitySearch } from '@/components/ui/EntitySearch'

export interface EntitySelectorProps {
  searchEndpoint: string
  onSelect: (entity: { wikidata_id: string; name: string }) => void
  onClear: () => void
  selectedEntity: { wikidata_id: string; name: string } | null
  placeholder?: string
  disabled?: boolean
}

export function EntitySelector({
  searchEndpoint,
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
      searchEndpoint={searchEndpoint}
      onSelect={onSelect}
      placeholder={placeholder}
      disabled={disabled}
    />
  )
}
