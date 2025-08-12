"use client";

import { useState, useRef, useEffect } from 'react';
import { Politician, Property, Position, Birthplace, EvaluationRequest, PropertyEvaluationItem, PositionEvaluationItem, BirthplaceEvaluationItem, ArchivedPageResponse } from '@/types';
import { submitEvaluations } from '@/lib/api';
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting';
import { highlightTextInScope, clearHighlights, ensureHighlightStyles } from '@/lib/textHighlighter';
import { useArchivedPageCache } from '@/contexts/ArchivedPageContext';
import { BaseEvaluationItem } from './BaseEvaluationItem';

interface PoliticianEvaluationProps {
  politician: Politician;
  accessToken: string;
  onNext: () => void;
}

export function PoliticianEvaluation({ politician, accessToken, onNext }: PoliticianEvaluationProps) {
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
    highlightText,
    isIframeLoaded,
    handleIframeLoad
  } = useIframeAutoHighlight(iframeRef, selectedProofLine);

  // Auto-load first statement source on component mount and ensure styles
  useEffect(() => {
    // Ensure highlight styles are injected into the main document once
    ensureHighlightStyles(document);
    
    const firstItem = politician.extracted_properties[0] || politician.extracted_positions[0] || politician.extracted_birthplaces[0];
    if (firstItem && firstItem.archived_page) {
      setSelectedArchivedPage(firstItem.archived_page);
      setSelectedProofLine(firstItem.proof_line || null);
      setActiveArchivedPageId(firstItem.archived_page.id);
    }
  }, [politician]);

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
    // Clear previous highlights from main document
    clearHighlights(document);
    
    // Clear previous highlights from iframe document if available
    if (iframeRef.current?.contentDocument) {
      clearHighlights(iframeRef.current.contentDocument);
    }
    
    // Set new archived page and highlight the proof line
    setSelectedArchivedPage(archivedPage);
    setActiveArchivedPageId(archivedPage.id);
    setSelectedProofLine(proofLine);
    
    // Highlight only in left panel (scoped highlighting)
    if (leftPanelRef.current) {
      highlightTextInScope(document, leftPanelRef.current, proofLine);
    }
    
    // Highlight in right panel (iframe) if loaded
    if (isIframeLoaded) {
      highlightText(proofLine);
    }
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

      const response = await submitEvaluations(evaluationData, accessToken);
      if (response.success) {
        onNext();
      } else {
        console.error('Evaluation errors:', response.errors);
        alert(`Error submitting evaluations: ${response.message}`);
      }
    } catch (error) {
      console.error('Error submitting evaluations:', error);
      alert('Error submitting evaluations. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex bg-gray-100 min-h-screen">
      {/* Left panel - Evaluation interface */}
      <div ref={leftPanelRef} className="w-[48rem] flex-shrink-0 bg-white shadow-lg p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{politician.name}</h1>
          {politician.wikidata_id && (
            <p className="text-gray-600">Wikidata ID: {politician.wikidata_id}</p>
          )}
        </div>

      {politician.extracted_properties.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Properties</h2>
          <div className="space-y-4">
            {politician.extracted_properties.map((property) => (
              <PropertyItem
                key={property.id}
                property={property}
                isConfirmed={confirmedProperties.has(property.id)}
                isDiscarded={discardedProperties.has(property.id)}
                onAction={(action) => handlePropertyAction(property.id, action)}
                onShowArchived={() => {
                  if (property.archived_page) {
                    setSelectedArchivedPage(property.archived_page);
                    setSelectedProofLine(property.proof_line || null);
                    setActiveArchivedPageId(property.archived_page.id);
                  }
                }}
                onHover={() => handlePropertyHover(property)}
                isActive={!!(property.archived_page && activeArchivedPageId === property.archived_page.id)}
              />
            ))}
          </div>
        </div>
      )}

      {politician.extracted_positions.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Political Positions</h2>
          <div className="space-y-4">
            {politician.extracted_positions.map((position) => (
              <PositionItem
                key={position.id}
                position={position}
                isConfirmed={confirmedPositions.has(position.id)}
                isDiscarded={discardedPositions.has(position.id)}
                onAction={(action) => handlePositionAction(position.id, action)}
                onShowArchived={() => {
                  if (position.archived_page) {
                    setSelectedArchivedPage(position.archived_page);
                    setSelectedProofLine(position.proof_line || null);
                    setActiveArchivedPageId(position.archived_page.id);
                  }
                }}
                onHover={() => handlePositionHover(position)}
                isActive={!!(position.archived_page && activeArchivedPageId === position.archived_page.id)}
              />
            ))}
          </div>
        </div>
      )}

      {politician.extracted_birthplaces.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Birthplaces</h2>
          <div className="space-y-4">
            {politician.extracted_birthplaces.map((birthplace) => (
              <BirthplaceItem
                key={birthplace.id}
                birthplace={birthplace}
                isConfirmed={confirmedBirthplaces.has(birthplace.id)}
                isDiscarded={discardedBirthplaces.has(birthplace.id)}
                onAction={(action) => handleBirthplaceAction(birthplace.id, action)}
                onShowArchived={() => {
                  if (birthplace.archived_page) {
                    setSelectedArchivedPage(birthplace.archived_page);
                    setSelectedProofLine(birthplace.proof_line || null);
                    setActiveArchivedPageId(birthplace.archived_page.id);
                  }
                }}
                onHover={() => handleBirthplaceHover(birthplace)}
                isActive={!!(birthplace.archived_page && activeArchivedPageId === birthplace.archived_page.id)}
              />
            ))}
          </div>
        </div>
      )}

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

      {/* Right panel - Archived page viewer */}
      <div className="flex-1 bg-gray-50 border-l border-gray-200 flex flex-col sticky" style={{ top: 'calc(4rem + 1px)', height: 'calc(100vh - 4rem - 1px)' }}>
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
        <div className="flex-1 overflow-hidden">
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

interface PropertyItemProps {
  property: Property;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
}

function PropertyItem({ property, isConfirmed, isDiscarded, onAction, onShowArchived, onHover, isActive = false }: PropertyItemProps) {
  return (
    <BaseEvaluationItem
      item={property}
      isConfirmed={isConfirmed}
      isDiscarded={isDiscarded}
      onAction={onAction}
      onShowArchived={onShowArchived}
      onHover={onHover}
      isActive={isActive}
    >
      <h3 className="font-medium text-gray-900">{property.type}</h3>
      <p className="text-gray-700 mt-1">{property.value}</p>
    </BaseEvaluationItem>
  );
}

interface PositionItemProps {
  position: Position;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
}

function PositionItem({ position, isConfirmed, isDiscarded, onAction, onShowArchived, onHover, isActive = false }: PositionItemProps) {
  return (
    <BaseEvaluationItem
      item={position}
      isConfirmed={isConfirmed}
      isDiscarded={isDiscarded}
      onAction={onAction}
      onShowArchived={onShowArchived}
      onHover={onHover}
      isActive={isActive}
    >
      <h3 className="font-medium text-gray-900">
        {position.wikidata_id ? (
          <a 
            href={`https://www.wikidata.org/wiki/${position.wikidata_id}`} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="hover:underline"
          >
            {position.position_name} <span className="text-gray-500 font-normal">({position.wikidata_id})</span>
          </a>
        ) : (
          position.position_name
        )}
      </h3>
      <p className="text-gray-700 mt-1">
        {position.start_date || 'Unknown'} - {position.end_date || 'Present'}
      </p>
    </BaseEvaluationItem>
  );
}

interface BirthplaceItemProps {
  birthplace: Birthplace;
  isConfirmed: boolean;
  isDiscarded: boolean;
  onAction: (action: 'confirm' | 'discard') => void;
  onShowArchived: () => void;
  onHover: () => void;
  isActive?: boolean;
}

function BirthplaceItem({ birthplace, isConfirmed, isDiscarded, onAction, onShowArchived, onHover, isActive = false }: BirthplaceItemProps) {
  return (
    <BaseEvaluationItem
      item={birthplace}
      isConfirmed={isConfirmed}
      isDiscarded={isDiscarded}
      onAction={onAction}
      onShowArchived={onShowArchived}
      onHover={onHover}
      isActive={isActive}
    >
      <h3 className="font-medium text-gray-900">
        {birthplace.wikidata_id ? (
          <a 
            href={`https://www.wikidata.org/wiki/${birthplace.wikidata_id}`} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="hover:underline"
          >
            {birthplace.location_name} <span className="text-gray-500 font-normal">({birthplace.wikidata_id})</span>
          </a>
        ) : (
          birthplace.location_name
        )}
      </h3>
    </BaseEvaluationItem>
  );
}