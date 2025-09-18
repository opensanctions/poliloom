"use client";

import { useState, useRef, useEffect } from 'react';
import { Politician, Property, Position, Birthplace, EvaluationRequest, PropertyEvaluationItem, PositionEvaluationItem, BirthplaceEvaluationItem, ArchivedPageResponse, EvaluationResponse } from '@/types';
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting';
import { highlightTextInScope } from '@/lib/textHighlighter';
import { useArchivedPageCache } from '@/contexts/ArchivedPageContext';
import { PropertyEvaluation } from './PropertyEvaluation';
import { PositionEvaluation } from './PositionEvaluation';
import { BirthplaceEvaluation } from './BirthplaceEvaluation';

interface PoliticianEvaluationProps {
  politician: Politician;
  onNext: () => void;
}

export function PoliticianEvaluation({ politician, onNext }: PoliticianEvaluationProps) {
  const [confirmedProperties, setConfirmedProperties] = useState<Set<string>>(new Set());
  const [discardedProperties, setDiscardedProperties] = useState<Set<string>>(new Set());
  const [confirmedPositions, setConfirmedPositions] = useState<Set<string>>(new Set());
  const [discardedPositions, setDiscardedPositions] = useState<Set<string>>(new Set());
  const [confirmedBirthplaces, setConfirmedBirthplaces] = useState<Set<string>>(new Set());
  const [discardedBirthplaces, setDiscardedBirthplaces] = useState<Set<string>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedArchivedPage, setSelectedArchivedPage] = useState<ArchivedPageResponse | null>(null);
  const [selectedProofLine, setSelectedProofLine] = useState<string | null>(null);
  const [activeArchivedPageId, setActiveArchivedPageId] = useState<string | null>(null);
  
  // Refs and hooks for iframe highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const leftPanelRef = useRef<HTMLDivElement | null>(null);
  const archivedPageCache = useArchivedPageCache();
  const {
    isIframeLoaded,
    handleIframeLoad,
    handleProofLineChange
  } = useIframeAutoHighlight(iframeRef, selectedProofLine);

  // Auto-load first statement source on component mount
  useEffect(() => {
    const firstItem = politician.extracted_properties[0] || politician.extracted_positions[0] || politician.extracted_birthplaces[0];
    if (firstItem && firstItem.archived_page) {
      setSelectedArchivedPage(firstItem.archived_page);
      setSelectedProofLine(firstItem.proof_line || null);
      setActiveArchivedPageId(firstItem.archived_page.id);
    }
  }, [politician]);

  // Update highlighting when proof line changes and iframe is loaded
  useEffect(() => {
    if (isIframeLoaded && selectedProofLine) {
      handleProofLineChange(selectedProofLine);
    }
  }, [selectedProofLine, isIframeLoaded, handleProofLineChange]);

  const handlePropertyAction = (propertyId: string, action: 'confirm' | 'discard') => {
    if (action === 'confirm') {
      setConfirmedProperties(prev => new Set(prev).add(propertyId));
      setDiscardedProperties(prev => {
        const newSet = new Set(prev);
        newSet.delete(propertyId);
        return newSet;
      });
    } else {
      setDiscardedProperties(prev => new Set(prev).add(propertyId));
      setConfirmedProperties(prev => {
        const newSet = new Set(prev);
        newSet.delete(propertyId);
        return newSet;
      });
    }
  };

  const handlePositionAction = (positionId: string, action: 'confirm' | 'discard') => {
    if (action === 'confirm') {
      setConfirmedPositions(prev => new Set(prev).add(positionId));
      setDiscardedPositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(positionId);
        return newSet;
      });
    } else {
      setDiscardedPositions(prev => new Set(prev).add(positionId));
      setConfirmedPositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(positionId);
        return newSet;
      });
    }
  };

  const handleBirthplaceAction = (birthplaceId: string, action: 'confirm' | 'discard') => {
    if (action === 'confirm') {
      setConfirmedBirthplaces(prev => new Set(prev).add(birthplaceId));
      setDiscardedBirthplaces(prev => {
        const newSet = new Set(prev);
        newSet.delete(birthplaceId);
        return newSet;
      });
    } else {
      setDiscardedBirthplaces(prev => new Set(prev).add(birthplaceId));
      setConfirmedBirthplaces(prev => {
        const newSet = new Set(prev);
        newSet.delete(birthplaceId);
        return newSet;
      });
    }
  };

  // Unified hover handler for all statement types
  const handleStatementHover = (proofLine: string, archivedPage: ArchivedPageResponse) => {
    // Highlight in left panel (main document) - always do this
    if (leftPanelRef.current && proofLine) {
      highlightTextInScope(document, leftPanelRef.current, proofLine);
    }
    
    // Only update iframe highlighting if we're already viewing this page
    if (activeArchivedPageId === archivedPage.id) {
      setSelectedProofLine(proofLine);
    }
    // Don't change the iframe source on hover
  };

  // Individual hover handlers that use the unified logic
  const handlePropertyHover = (property: Property) => {
    if (property.proof_line && property.archived_page) {
      handleStatementHover(property.proof_line, property.archived_page);
    }
  };

  const handlePositionHover = (position: Position) => {
    if (position.proof_line && position.archived_page) {
      handleStatementHover(position.proof_line, position.archived_page);
    }
  };

  const handleBirthplaceHover = (birthplace: Birthplace) => {
    if (birthplace.proof_line && birthplace.archived_page) {
      handleStatementHover(birthplace.proof_line, birthplace.archived_page);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const propertyEvaluations: PropertyEvaluationItem[] = [
        ...Array.from(confirmedProperties).map(id => ({
          id,
          is_confirmed: true
        })),
        ...Array.from(discardedProperties).map(id => ({
          id,
          is_confirmed: false
        }))
      ];

      const positionEvaluations: PositionEvaluationItem[] = [
        ...Array.from(confirmedPositions).map(id => ({
          id,
          is_confirmed: true
        })),
        ...Array.from(discardedPositions).map(id => ({
          id,
          is_confirmed: false
        }))
      ];

      const birthplaceEvaluations: BirthplaceEvaluationItem[] = [
        ...Array.from(confirmedBirthplaces).map(id => ({
          id,
          is_confirmed: true
        })),
        ...Array.from(discardedBirthplaces).map(id => ({
          id,
          is_confirmed: false
        }))
      ];

      const evaluationData: EvaluationRequest = {
        property_evaluations: propertyEvaluations,
        position_evaluations: positionEvaluations,
        birthplace_evaluations: birthplaceEvaluations
      };

      const response = await fetch('/api/politicians/evaluate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
        console.error('Evaluation errors:', result.errors);
        alert(`Error submitting evaluations: ${result.message}`);
      }
    } catch (error) {
      console.error('Error submitting evaluations:', error);
      alert('Error submitting evaluations. Please try again.');
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
                <a href={`https://www.wikidata.org/wiki/${politician.wikidata_id}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {politician.name} <span className="text-gray-500 font-normal">({politician.wikidata_id})</span>
                </a>
              </h1>
            ) : (
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{politician.name}</h1>
            )}
          </div>

      <PropertyEvaluation
        wikidataProperties={politician.wikidata_properties}
        extractedProperties={politician.extracted_properties}
        confirmedProperties={confirmedProperties}
        discardedProperties={discardedProperties}
        onAction={handlePropertyAction}
        onShowArchived={(property) => {
          if (property.archived_page) {
            setSelectedArchivedPage(property.archived_page);
            setSelectedProofLine(property.proof_line || null);
            setActiveArchivedPageId(property.archived_page.id);
          }
        }}
        onHover={handlePropertyHover}
        activeArchivedPageId={activeArchivedPageId}
      />

      <PositionEvaluation
        wikidataPositions={politician.wikidata_positions}
        extractedPositions={politician.extracted_positions}
        confirmedPositions={confirmedPositions}
        discardedPositions={discardedPositions}
        onAction={handlePositionAction}
        onShowArchived={(position) => {
          if (position.archived_page) {
            setSelectedArchivedPage(position.archived_page);
            setSelectedProofLine(position.proof_line || null);
            setActiveArchivedPageId(position.archived_page.id);
          }
        }}
        onHover={handlePositionHover}
        activeArchivedPageId={activeArchivedPageId}
      />

      <BirthplaceEvaluation
        wikidataBirthplaces={politician.wikidata_birthplaces}
        extractedBirthplaces={politician.extracted_birthplaces}
        confirmedBirthplaces={confirmedBirthplaces}
        discardedBirthplaces={discardedBirthplaces}
        onAction={handleBirthplaceAction}
        onShowArchived={(birthplace) => {
          if (birthplace.archived_page) {
            setSelectedArchivedPage(birthplace.archived_page);
            setSelectedProofLine(birthplace.proof_line || null);
            setActiveArchivedPageId(birthplace.archived_page.id);
          }
        }}
        onHover={handleBirthplaceHover}
        activeArchivedPageId={activeArchivedPageId}
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
              {isSubmitting ? 'Submitting...' : 'Submit Evaluations & Next'}
            </button>
          </div>
        </div>
      </div>

      {/* Right panel - Archived page viewer */}
      <div className="bg-gray-50 border-l border-gray-200 grid grid-rows-[auto_1fr] min-h-0">
        <div className="p-4 border-b border-gray-200 bg-white">
          <h3 className="text-lg font-semibold text-gray-900">
            {selectedArchivedPage ? 'Archived Page' : 'Select an item to view source'}
          </h3>
          {selectedArchivedPage && (
            <div className="mt-2">
              <p className="text-sm text-gray-600">
                Source: <a href={selectedArchivedPage.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  {selectedArchivedPage.url}
                </a>
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Fetched: {new Date(selectedArchivedPage.fetch_timestamp).toLocaleDateString()}
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
                <p>Click &ldquo;View Source&rdquo; on any item to see the archived page</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}