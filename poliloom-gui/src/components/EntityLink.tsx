interface EntityLinkProps {
  entityId: string;
  entityName?: string;
  fallbackName?: string;
}

export function EntityLink({ entityId, entityName, fallbackName = "Unknown" }: EntityLinkProps) {
  const displayName = entityName || entityId || fallbackName;

  return (
    <a
      href={`https://www.wikidata.org/wiki/${entityId}`}
      target="_blank"
      rel="noopener noreferrer"
      className="hover:underline"
    >
      {displayName} <span className="text-gray-500 font-normal">({entityId})</span>
    </a>
  );
}