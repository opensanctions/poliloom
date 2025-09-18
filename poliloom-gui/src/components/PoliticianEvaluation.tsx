"use client";

import { useState, useRef, useEffect } from "react";
import {
  Politician,
  PropertyStatement,
  PositionStatement,
  BirthplaceStatement,
  EvaluationRequest,
  PropertyEvaluationItem,
  PositionEvaluationItem,
  BirthplaceEvaluationItem,
  ArchivedPageResponse,
  EvaluationResponse,
} from "@/types";
import { useIframeAutoHighlight } from "@/hooks/useIframeHighlighting";
import { highlightTextInScope } from "@/lib/textHighlighter";
import { useArchivedPageCache } from "@/contexts/ArchivedPageContext";
import { PropertyEvaluation } from "./PropertyEvaluation";
import { PositionEvaluation } from "./PositionEvaluation";
import { BirthplaceEvaluation } from "./BirthplaceEvaluation";

interface PoliticianEvaluationProps {
  politician: Politician;
  onNext: () => void;
}

export function PoliticianEvaluation({
  politician,
  onNext,
}: PoliticianEvaluationProps) {
  const [propertyEvaluations, setPropertyEvaluations] = useState<
    Map<string, boolean>
  >(new Map());
  const [positionEvaluations, setPositionEvaluations] = useState<
    Map<string, boolean>
  >(new Map());
  const [birthplaceEvaluations, setBirthplaceEvaluations] = useState<
    Map<string, boolean>
  >(new Map());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedArchivedPage, setSelectedArchivedPage] =
    useState<ArchivedPageResponse | null>(null);
  const [selectedProofLine, setSelectedProofLine] = useState<string | null>(
    null,
  );

  // Helper function to find first statement with archived page
  const findFirstStatementWithArchive = (
    statements: (PropertyStatement | PositionStatement | BirthplaceStatement)[],
  ) => {
    return statements.find((s) => s.archived_page);
  };

  // Refs and hooks for iframe highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const leftPanelRef = useRef<HTMLDivElement | null>(null);
  const archivedPageCache = useArchivedPageCache();
  const { isIframeLoaded, handleIframeLoad, handleProofLineChange } =
    useIframeAutoHighlight(iframeRef, selectedProofLine);

  // Auto-load first archived page found
  useEffect(() => {
    const allStatements = [
      ...politician.properties.flatMap((p) => p.statements),
      ...politician.positions.flatMap((p) => p.statements),
      ...politician.birthplaces.flatMap((b) => b.statements),
    ];

    const firstWithArchive = findFirstStatementWithArchive(allStatements);
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

  const handlePropertyAction = (
    propertyId: string,
    action: "confirm" | "discard",
  ) => {
    setPropertyEvaluations((prev) => {
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

  const handlePositionAction = (
    positionId: string,
    action: "confirm" | "discard",
  ) => {
    setPositionEvaluations((prev) => {
      const newMap = new Map(prev);
      const currentValue = newMap.get(positionId);
      const targetValue = action === "confirm";

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(positionId);
      } else {
        // Set new value
        newMap.set(positionId, targetValue);
      }
      return newMap;
    });
  };

  const handleBirthplaceAction = (
    birthplaceId: string,
    action: "confirm" | "discard",
  ) => {
    setBirthplaceEvaluations((prev) => {
      const newMap = new Map(prev);
      const currentValue = newMap.get(birthplaceId);
      const targetValue = action === "confirm";

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(birthplaceId);
      } else {
        // Set new value
        newMap.set(birthplaceId, targetValue);
      }
      return newMap;
    });
  };

  // Unified hover handler for all statement types
  const handleStatementHover = (
    statement: PropertyStatement | PositionStatement | BirthplaceStatement,
  ) => {
    // Only update proof line (which triggers highlighting) if we're viewing this statement's archived page
    if (
      statement.archived_page &&
      selectedArchivedPage?.id === statement.archived_page.id &&
      statement.proof_line
    ) {
      setSelectedProofLine(statement.proof_line);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const propertyEvaluationItems: PropertyEvaluationItem[] = Array.from(
        propertyEvaluations.entries(),
      ).map(([id, isConfirmed]) => ({
        id,
        is_confirmed: isConfirmed,
      }));

      const positionEvaluationItems: PositionEvaluationItem[] = Array.from(
        positionEvaluations.entries(),
      ).map(([id, isConfirmed]) => ({
        id,
        is_confirmed: isConfirmed,
      }));

      const birthplaceEvaluationItems: BirthplaceEvaluationItem[] = Array.from(
        birthplaceEvaluations.entries(),
      ).map(([id, isConfirmed]) => ({
        id,
        is_confirmed: isConfirmed,
      }));

      const evaluationData: EvaluationRequest = {
        property_evaluations: propertyEvaluationItems,
        position_evaluations: positionEvaluationItems,
        birthplace_evaluations: birthplaceEvaluationItems,
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

          <PropertyEvaluation
            properties={politician.properties}
            evaluations={propertyEvaluations}
            onAction={handlePropertyAction}
            onShowArchived={(property) => {
              if (property.archived_page) {
                setSelectedArchivedPage(property.archived_page);
                setSelectedProofLine(property.proof_line || null);
              }
            }}
            onHover={handleStatementHover}
            activeArchivedPageId={selectedArchivedPage?.id || null}
          />

          <PositionEvaluation
            positions={politician.positions}
            evaluations={positionEvaluations}
            onAction={handlePositionAction}
            onShowArchived={(position) => {
              if (position.archived_page) {
                setSelectedArchivedPage(position.archived_page);
                setSelectedProofLine(position.proof_line || null);
              }
            }}
            onHover={handleStatementHover}
            activeArchivedPageId={selectedArchivedPage?.id || null}
          />

          <BirthplaceEvaluation
            birthplaces={politician.birthplaces}
            evaluations={birthplaceEvaluations}
            onAction={handleBirthplaceAction}
            onShowArchived={(birthplace) => {
              if (birthplace.archived_page) {
                setSelectedArchivedPage(birthplace.archived_page);
                setSelectedProofLine(birthplace.proof_line || null);
              }
            }}
            onHover={handleStatementHover}
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
