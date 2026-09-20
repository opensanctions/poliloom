interface PoliticianHeaderProps {
  name: string
  wikidataId?: string
}

export function PoliticianHeader({ name, wikidataId }: PoliticianHeaderProps) {
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
