import { useState, useEffect } from "react";

interface WikidataMetadataProps {
  qualifiers?: Record<string, unknown>;
  references?: Array<Record<string, unknown>>;
  isDiscarding?: boolean;
}

export function WikidataMetadata({
  qualifiers,
  references,
  isDiscarding = false,
}: WikidataMetadataProps) {
  const [openSection, setOpenSection] = useState<
    "qualifiers" | "references" | null
  >(null);
  const [wasAutoOpened, setWasAutoOpened] = useState(false);

  const hasQualifiers = qualifiers && Object.keys(qualifiers).length > 0;
  const hasReferences = references && references.length > 0;

  // Auto-open the panel when discarding
  useEffect(() => {
    if (isDiscarding && (hasQualifiers || hasReferences)) {
      // Only open a panel if none is currently open
      setOpenSection(prev => {
        if (prev === null) {
          setWasAutoOpened(true);
          // Prefer qualifiers if both exist, otherwise references
          return hasQualifiers ? "qualifiers" : "references";
        }
        return prev; // Keep current section open
      });
    } else if (!isDiscarding && wasAutoOpened) {
      // Close panel if it was auto-opened
      setOpenSection(null);
      setWasAutoOpened(false);
    }
  }, [isDiscarding, hasQualifiers, hasReferences, wasAutoOpened]);

  if (!hasQualifiers && !hasReferences) {
    return <div className="text-sm text-gray-700 mt-2">No metadata</div>;
  }

  const handleToggle = (section: "qualifiers" | "references") => {
    const newOpenSection = openSection === section ? null : section;
    setOpenSection(newOpenSection);

    // Only reset auto-open tracking if we're opening a new section
    if (newOpenSection !== null) {
      setWasAutoOpened(false);
    }
  };

  return (
    <div className="mt-2">
      <div className="flex gap-4 text-sm">
        {hasQualifiers && (
          <button
            className="font-medium cursor-pointer flex items-center gap-1 text-gray-700 hover:text-gray-900"
            onClick={() => handleToggle("qualifiers")}
          >
            <span
              className={`transition-transform ${openSection === "qualifiers" ? "" : "-rotate-90"}`}
            >
              ▼
            </span>
            Qualifiers
          </button>
        )}
        {hasReferences && (
          <button
            className="font-medium cursor-pointer flex items-center gap-1 text-gray-700 hover:text-gray-900"
            onClick={() => handleToggle("references")}
          >
            <span
              className={`transition-transform ${openSection === "references" ? "" : "-rotate-90"}`}
            >
              ▼
            </span>
            References
          </button>
        )}
      </div>
      {openSection === "qualifiers" && hasQualifiers && (
        <div className="mt-2">
          <div className={`relative p-2 rounded ${(isDiscarding || wasAutoOpened) ? "bg-red-900" : "bg-gray-700"}`}>
            {(isDiscarding || wasAutoOpened) && (
              <div className="absolute top-2 right-2 text-white text-xs font-medium">
                Metadata will be lost ⚠
              </div>
            )}
            <pre className="text-white text-xs overflow-x-auto">
              <code>{JSON.stringify(qualifiers, null, 2)}</code>
            </pre>
          </div>
        </div>
      )}
      {openSection === "references" && hasReferences && (
        <div className="mt-2">
          <div className={`relative p-2 rounded ${(isDiscarding || wasAutoOpened) ? "bg-red-900" : "bg-gray-700"}`}>
            {(isDiscarding || wasAutoOpened) && (
              <div className="absolute top-2 right-2 text-white text-xs font-medium">
                Metadata will be lost ⚠
              </div>
            )}
            <pre className="text-white text-xs overflow-x-auto">
              <code>{JSON.stringify(references, null, 2)}</code>
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
