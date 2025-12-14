interface EntityLinkProps {
  entityId: string
  entityName: string
}

export function EntityLink({ entityId, entityName }: EntityLinkProps) {
  return (
    <a
      href={`https://www.wikidata.org/wiki/${entityId}`}
      target="_blank"
      rel="noopener noreferrer"
      className="hover:underline font-bold capitalize"
    >
      {entityName} <span className="text-foreground-muted font-normal">({entityId})</span>
    </a>
  )
}
