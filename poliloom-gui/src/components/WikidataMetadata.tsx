function MetadataSectionButton({
  title,
  sectionKey,
  isOpen,
  onToggle,
}: {
  title: string
  sectionKey: 'qualifiers' | 'references'
  isOpen: boolean
  onToggle: (section: 'qualifiers' | 'references') => void
}) {
  return (
    <button
      className="font-medium cursor-pointer flex items-center gap-1 text-red-600 hover:text-red-700"
      onClick={() => onToggle(sectionKey)}
    >
      <span className={`transition-transform ${isOpen ? '' : '-rotate-90'}`}>▼</span>
      {title}
    </button>
  )
}

export function WikidataMetadataButtons({
  qualifiers,
  references,
  openSection,
  onToggle,
}: {
  qualifiers?: Record<string, unknown>
  references?: Array<Record<string, unknown>>
  openSection: 'qualifiers' | 'references' | null
  onToggle: (section: 'qualifiers' | 'references') => void
}) {
  const hasQualifiers = qualifiers && Object.keys(qualifiers).length > 0
  const hasReferences = references && references.length > 0

  if (!hasQualifiers && !hasReferences) {
    return null
  }

  return (
    <div className="flex gap-4 text-sm items-center">
      {hasQualifiers && (
        <MetadataSectionButton
          title="Qualifiers"
          sectionKey="qualifiers"
          isOpen={openSection === 'qualifiers'}
          onToggle={onToggle}
        />
      )}
      {hasReferences && (
        <MetadataSectionButton
          title="References"
          sectionKey="references"
          isOpen={openSection === 'references'}
          onToggle={onToggle}
        />
      )}
      {openSection === null && (hasQualifiers || hasReferences) && <span>⚠️</span>}
    </div>
  )
}

export function WikidataMetadataPanel({
  qualifiers,
  references,
  openSection,
}: {
  qualifiers?: Record<string, unknown>
  references?: Array<Record<string, unknown>>
  openSection: 'qualifiers' | 'references' | null
}) {
  const hasQualifiers = qualifiers && Object.keys(qualifiers).length > 0
  const hasReferences = references && references.length > 0

  if (openSection === null) return null

  const renderPanel = (data: Record<string, unknown> | Array<Record<string, unknown>>) => (
    <div className="relative p-2 rounded bg-red-900">
      <div className="absolute top-2 right-2 text-white text-xs">Metadata will be lost ⚠️</div>
      <pre className="text-white text-xs overflow-x-auto">
        <code>{JSON.stringify(data, null, 2)}</code>
      </pre>
    </div>
  )

  return (
    <>
      {openSection === 'qualifiers' && hasQualifiers && renderPanel(qualifiers!)}
      {openSection === 'references' && hasReferences && renderPanel(references!)}
    </>
  )
}
