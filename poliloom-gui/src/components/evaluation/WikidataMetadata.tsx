import { RestSnak, RestStatement } from '@/types'

type StatementReferences = RestStatement['references']

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
      className="font-medium cursor-pointer flex items-center gap-1 text-foreground-muted hover:text-foreground"
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
  qualifiers: RestSnak[]
  references: StatementReferences
  openSection: 'qualifiers' | 'references' | null
  onToggle: (section: 'qualifiers' | 'references') => void
}) {
  const hasQualifiers = qualifiers.length > 0
  const hasReferences = references.length > 0

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
    </div>
  )
}

export function WikidataMetadataPanel({
  qualifiers,
  references,
  openSection,
}: {
  qualifiers: RestSnak[]
  references: StatementReferences
  openSection: 'qualifiers' | 'references' | null
}) {
  const hasQualifiers = qualifiers.length > 0
  const hasReferences = references.length > 0

  if (openSection === null) return null

  const renderPanel = (data: unknown) => (
    <div className="relative p-2 rounded bg-surface-muted">
      <pre className="text-foreground-secondary text-xs overflow-x-auto">
        <code>{JSON.stringify(data, null, 2)}</code>
      </pre>
    </div>
  )

  return (
    <>
      {openSection === 'qualifiers' && hasQualifiers && renderPanel(qualifiers)}
      {openSection === 'references' && hasReferences && renderPanel(references)}
    </>
  )
}
