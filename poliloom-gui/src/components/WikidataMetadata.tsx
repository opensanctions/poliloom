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

  const hasQualifiers = qualifiers && Object.keys(qualifiers).length > 0;
  const hasReferences = references && references.length > 0;

  // Auto-open the panel when discarding
  useEffect(() => {
    if (isDiscarding && (hasQualifiers || hasReferences)) {
      // Prefer qualifiers if both exist, otherwise references
      setOpenSection(hasQualifiers ? "qualifiers" : "references");
    } else if (!isDiscarding) {
      setOpenSection(null);
    }
  }, [isDiscarding, hasQualifiers, hasReferences]);

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
            className={`font-medium cursor-pointer flex items-center gap-1 ${
              isDiscarding
                ? "text-red-600 hover:text-red-700"
                : "text-gray-700 hover:text-gray-900"
            }`}
            onClick={() => handleToggle("qualifiers")}
          >
            <span
              className={`transition-transform ${openSection === "qualifiers" ? "" : "-rotate-90"}`}
            >
              ▼
            </span>
            Qualifiers{isDiscarding && " ❗"}
          </button>
        )}
        {hasReferences && (
          <button
            className={`font-medium cursor-pointer flex items-center gap-1 ${
              isDiscarding
                ? "text-red-600 hover:text-red-700"
                : "text-gray-700 hover:text-gray-900"
            }`}
            onClick={() => handleToggle("references")}
          >
            <span
              className={`transition-transform ${openSection === "references" ? "" : "-rotate-90"}`}
            >
              ▼
            </span>
            References{isDiscarding && " ❗"}
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
