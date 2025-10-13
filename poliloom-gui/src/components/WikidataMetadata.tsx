import { useState, useLayoutEffect } from 'react'

interface WikidataMetadataProps {
  qualifiers?: Record<string, unknown>
  references?: Array<Record<string, unknown>>
  isDiscarding?: boolean
  shouldAutoOpen?: boolean
}

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
      className="font-medium cursor-pointer flex items-center gap-1 text-gray-700 hover:text-gray-900"
      onClick={() => onToggle(sectionKey)}
    >
      <span className={`transition-transform ${isOpen ? '' : '-rotate-90'}`}>▼</span>
      {title}
    </button>
  )
}

function MetadataSectionPanel({
  data,
  isDiscarding,
}: {
  data: Record<string, unknown> | Array<Record<string, unknown>>
  isDiscarding: boolean
}) {
  return (
    <div className="mt-2">
      <div className={`relative p-2 rounded ${isDiscarding ? 'bg-red-900' : 'bg-gray-700'}`}>
        {isDiscarding && (
          <div className="absolute top-2 right-2 text-white text-xs">Metadata will be lost ⚠</div>
        )}
        <pre className="text-white text-xs overflow-x-auto">
          <code>{JSON.stringify(data, null, 2)}</code>
        </pre>
      </div>
    </div>
  )
}

export function WikidataMetadata({
  qualifiers,
  references,
  isDiscarding = false,
  shouldAutoOpen = true,
}: WikidataMetadataProps) {
  const [openSection, setOpenSection] = useState<'qualifiers' | 'references' | null>(null)
  const [wasAutoOpened, setWasAutoOpened] = useState(false)

  const hasQualifiers = qualifiers && Object.keys(qualifiers).length > 0
  const hasReferences = references && references.length > 0

  // Auto-open the panel when discarding
  // Note: openSection is intentionally excluded from dependencies to avoid re-triggering
  // the effect when users manually toggle the panel (which would reopen it immediately)
  useLayoutEffect(() => {
    if (shouldAutoOpen && isDiscarding && (hasQualifiers || hasReferences)) {
      // Only open a panel if none is currently open
      if (openSection === null) {
        setWasAutoOpened(true)
        setOpenSection(hasQualifiers ? 'qualifiers' : 'references')
      }
    } else if (!isDiscarding && wasAutoOpened) {
      // Close panel if it was auto-opened
      setOpenSection(null)
      setWasAutoOpened(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldAutoOpen, isDiscarding, hasQualifiers, hasReferences, wasAutoOpened])

  if (!hasQualifiers && !hasReferences) {
    return <div className="text-sm text-gray-700 mt-2">No metadata</div>
  }

  const handleToggle = (section: 'qualifiers' | 'references') => {
    const newOpenSection = openSection === section ? null : section
    setOpenSection(newOpenSection)

    // Only reset auto-open tracking if we're opening a new section
    if (newOpenSection !== null) {
      setWasAutoOpened(false)
    }
  }

  return (
    <div className="mt-2">
      <div className="flex gap-4 text-sm items-center">
        {hasQualifiers && (
          <MetadataSectionButton
            title="Qualifiers"
            sectionKey="qualifiers"
            isOpen={openSection === 'qualifiers'}
            onToggle={handleToggle}
          />
        )}
        {hasReferences && (
          <MetadataSectionButton
            title="References"
            sectionKey="references"
            isOpen={openSection === 'references'}
            onToggle={handleToggle}
          />
        )}
        {isDiscarding && openSection === null && (hasQualifiers || hasReferences) && (
          <span className="text-red-600 text-xs font-medium">⚠ Metadata will be lost</span>
        )}
      </div>
      {openSection === 'qualifiers' && hasQualifiers && (
        <MetadataSectionPanel data={qualifiers!} isDiscarding={isDiscarding} />
      )}
      {openSection === 'references' && hasReferences && (
        <MetadataSectionPanel data={references!} isDiscarding={isDiscarding} />
      )}
    </div>
  )
}
