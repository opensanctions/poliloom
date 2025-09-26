import { useState } from "react";

interface WikidataMetadataProps {
  qualifiers?: Record<string, unknown>;
  references?: Array<Record<string, unknown>>;
}

export function WikidataMetadata({
  qualifiers,
  references,
}: WikidataMetadataProps) {
  const [openSection, setOpenSection] = useState<
    "qualifiers" | "references" | null
  >(null);

  const hasQualifiers = qualifiers && Object.keys(qualifiers).length > 0;
  const hasReferences = references && references.length > 0;

  if (!hasQualifiers && !hasReferences) {
    return <div className="text-sm text-gray-700 mt-2">No metadata</div>;
  }

  const handleToggle = (section: "qualifiers" | "references") => {
    setOpenSection(openSection === section ? null : section);
  };

  return (
    <div className="mt-2">
      <div className="flex gap-4 text-sm">
        {hasQualifiers && (
          <button
            className="font-medium text-gray-700 cursor-pointer hover:text-gray-900 flex items-center gap-1"
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
            className="font-medium text-gray-700 cursor-pointer hover:text-gray-900 flex items-center gap-1"
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
          <pre className="bg-gray-700 text-white p-2 rounded text-xs overflow-x-auto">
            <code>{JSON.stringify(qualifiers, null, 2)}</code>
          </pre>
        </div>
      )}
      {openSection === "references" && hasReferences && (
        <div className="mt-2">
          <pre className="bg-gray-700 text-white p-2 rounded text-xs overflow-x-auto">
            <code>{JSON.stringify(references, null, 2)}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
