"use client";

import { useState, useRef, useEffect } from "react";
import {
  Politician,
  Property,
  EvaluationRequest,
  EvaluationItem,
  ArchivedPageResponse,
  EvaluationResponse,
} from "@/types";
import { useIframeAutoHighlight } from "@/hooks/useIframeHighlighting";
import { highlightTextInScope } from "@/lib/textHighlighter";
import { useArchivedPageCache } from "@/contexts/ArchivedPageContext";
import { PropertiesEvaluation } from "./PropertiesEvaluation";

interface PoliticianEvaluationProps {
  politician: Politician;
  onNext: () => void;
}

export function PoliticianEvaluation({
  politician,
  onNext,
}: PoliticianEvaluationProps) {
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(
    new Map(),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedArchivedPage, setSelectedArchivedPage] =
    useState<ArchivedPageResponse | null>(null);
  const [selectedProofLine, setSelectedProofLine] = useState<string | null>(
    null,
  );

  // Helper function to find first property with archived page
  const findFirstPropertyWithArchive = (properties: Property[]) => {
    return properties.find((p) => p.archived_page);
  };

  // Refs and hooks for iframe highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const leftPanelRef = useRef<HTMLDivElement | null>(null);
  const archivedPageCache = useArchivedPageCache();
  const { isIframeLoaded, handleIframeLoad, handleProofLineChange } =
    useIframeAutoHighlight(iframeRef, selectedProofLine);

  // Auto-load first archived page found
  useEffect(() => {
    const firstWithArchive = findFirstPropertyWithArchive(politician.properties);
    if (firstWithArchive && firstWithArchive.archived_page) {
      setSelectedArchivedPage(firstWithArchive.archived_page);
      setSelectedProofLine(firstWithArchive.proof_line || null);
    }
  }, [politician]);

  // Update highlighting when proof line changes
  useEffect(() => {
    // Left panel highlighting - always do this when proof line changes
    if (leftPanelRef.current && selectedProofLine) {
      highlightTextInScope(document, leftPanelRef.current, selectedProofLine);
    }

    // Iframe highlighting - only when iframe is loaded
    if (isIframeLoaded && selectedProofLine) {
      handleProofLineChange(selectedProofLine);
    }
  }, [selectedProofLine, isIframeLoaded, handleProofLineChange]);

  const handleEvaluate = (propertyId: string, action: "confirm" | "discard") => {
    setEvaluations((prev) => {
      const newMap = new Map(prev);
      const currentValue = newMap.get(propertyId);
      const targetValue = action === "confirm";

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(propertyId);
      } else {
        // Set new value
        newMap.set(propertyId, targetValue);
      }
      return newMap;
    });
  };

  // Unified hover handler for all property types
  const handlePropertyHover = (property: Property) => {
    // Only update proof line (which triggers highlighting) if we're viewing this property's archived page
    if (
      property.archived_page &&
      selectedArchivedPage?.id === property.archived_page.id &&
      property.proof_line
    ) {
      setSelectedProofLine(property.proof_line);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const evaluationItems: EvaluationItem[] = Array.from(
        evaluations.entries(),
      ).map(([id, isConfirmed]) => ({
        id,
        is_confirmed: isConfirmed,
      }));

      const evaluationData: EvaluationRequest = {
        evaluations: evaluationItems,
      };

      const response = await fetch("/api/politicians/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(evaluationData),
      });

      if (!response.ok) {
        throw new Error(`Failed to submit evaluations: ${response.statusText}`);
      }

      const result: EvaluationResponse = await response.json();
      if (result.success) {
        onNext();
      } else {
        console.error("Evaluation errors:", result.errors);
        alert(`Error submitting evaluations: ${result.message}`);
      }
    } catch (error) {
      console.error("Error submitting evaluations:", error);
      alert("Error submitting evaluations. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="grid grid-cols-[48rem_1fr] bg-gray-100 min-h-0">
      {/* Left panel - Evaluation interface */}
      <div className="bg-white shadow-lg grid grid-rows-[1fr_auto] min-h-0">
        {/* Scrollable content area */}
        <div ref={leftPanelRef} className="overflow-y-auto min-h-0 p-6">
          <div className="mb-6">
            {politician.wikidata_id ? (
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                <a
                  href={`https://www.wikidata.org/wiki/${politician.wikidata_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline"
                >
                  {politician.name}{" "}
                  <span className="text-gray-500 font-normal">
                    ({politician.wikidata_id})
                  </span>
                </a>
              </h1>
            ) : (
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                {politician.name}
              </h1>
            )}
          </div>

          <PropertiesEvaluation
            properties={politician.properties}
            evaluations={evaluations}
            onAction={handleEvaluate}
            onShowArchived={(property) => {
              if (property.archived_page) {
                setSelectedArchivedPage(property.archived_page);
                setSelectedProofLine(property.proof_line || null);
              }
            }}
            onHover={handlePropertyHover}
            activeArchivedPageId={selectedArchivedPage?.id || null}
          />
        </div>

        {/* Fixed button at bottom */}
        <div className="p-6 border-t border-gray-200">
          <div className="flex justify-end">
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Submitting..." : "Submit Evaluations & Next"}
            </button>
          </div>
        </div>
      </div>

      {/* Right panel - Archived page viewer */}
      <div className="bg-gray-50 border-l border-gray-200 grid grid-rows-[auto_1fr] min-h-0">
        <div className="p-4 border-b border-gray-200 bg-white">
          <h3 className="text-lg font-semibold text-gray-900">
            {selectedArchivedPage
              ? "Archived Page"
              : "Select an item to view source"}
          </h3>
          {selectedArchivedPage && (
            <div className="mt-2">
              <p className="text-sm text-gray-600">
                Source:{" "}
                <a
                  href={selectedArchivedPage.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  {selectedArchivedPage.url}
                </a>
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Fetched:{" "}
                {new Date(
                  selectedArchivedPage.fetch_timestamp,
                ).toLocaleDateString()}
              </p>
            </div>
          )}
        </div>
        <div className="overflow-hidden min-h-0">
          {selectedArchivedPage ? (
            <iframe
              ref={iframeRef}
              src={`/api/archived-pages/${selectedArchivedPage.id}/html`}
              className="w-full h-full border-0"
              title="Archived Page"
              sandbox="allow-scripts allow-same-origin"
              onLoad={() => {
                archivedPageCache.markPageAsLoaded(selectedArchivedPage.id);
                handleIframeLoad();
              }}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <p className="text-lg mb-2">📄</p>
                <p>
                  Click &ldquo;View Source&rdquo; on any item to see the
                  archived page
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
