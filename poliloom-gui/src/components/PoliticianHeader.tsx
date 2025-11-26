interface PoliticianHeaderProps {
  name: string
  wikidataId?: string
}

export function PoliticianHeader({ name, wikidataId }: PoliticianHeaderProps) {
  if (wikidataId) {
    return (
      <h1 className="text-2xl font-bold text-gray-900 mb-2">
        <a
          href={`https://www.wikidata.org/wiki/${wikidataId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          {name} <span className="text-gray-500 font-normal">({wikidataId})</span>
        </a>
      </h1>
    )
  }

  return <h1 className="text-2xl font-bold text-gray-900 mb-2">{name}</h1>
}
