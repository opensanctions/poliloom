import { Input } from '@/components/ui/Input'

interface PoliticianHeaderProps {
  name: string
  wikidataId?: string
  onNameChange?: (name: string) => void
}

export function PoliticianHeader({ name, wikidataId, onNameChange }: PoliticianHeaderProps) {
  if (onNameChange) {
    return (
      <Input
        value={name}
        onChange={(e) => onNameChange(e.target.value)}
        placeholder="Politician name"
      />
    )
  }

  return (
    <h1 className="text-2xl font-bold text-foreground">
      {wikidataId ? (
        <a
          href={`https://www.wikidata.org/wiki/${wikidataId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          {name} <span className="text-foreground-muted font-normal">({wikidataId})</span>
        </a>
      ) : (
        name
      )}
    </h1>
  )
}
