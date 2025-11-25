'use client'

import { useState, useRef, useEffect } from 'react'
import { Politician, Property, EvaluationItem, ArchivedPageResponse } from '@/types'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { useArchivedPageCache } from '@/contexts/ArchivedPageContext'
import { useEvaluation } from '@/contexts/EvaluationContext'
import { Button } from './Button'
import { PropertiesEvaluation } from './PropertiesEvaluation'

interface PoliticianEvaluationProps {
  politician: Politician
}

export function PoliticianEvaluation({ politician }: PoliticianEvaluationProps) {
  const { completedCount, sessionGoal, submitEvaluation, skipPolitician } = useEvaluation()
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [selectedArchivedPage, setSelectedArchivedPage] = useState<ArchivedPageResponse | null>(
    null,
  )
  const [selectedQuotes, setSelectedQuotes] = useState<string[] | null>(null)

  // Helper function to find first new property with archived page
  // Only new properties (without statement_id) show the View button
  const findFirstPropertyWithArchive = (properties: Property[]) => {
    return properties.find((p) => p.archived_page && !p.statement_id)
  }

  // Refs and hooks for iframe highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const leftPanelRef = useRef<HTMLDivElement | null>(null)
  const archivedPageCache = useArchivedPageCache()
  const { isIframeLoaded, handleIframeLoad, handleQuotesChange } = useIframeAutoHighlight(
    iframeRef,
    selectedQuotes,
  )

  // Auto-load first archived page found
  useEffect(() => {
    const firstWithArchive = findFirstPropertyWithArchive(politician.properties)
    if (firstWithArchive && firstWithArchive.archived_page) {
      setSelectedArchivedPage(firstWithArchive.archived_page)
      setSelectedQuotes(firstWithArchive.supporting_quotes || null)
    }
  }, [politician])

  // Update highlighting when supporting quotes change
  useEffect(() => {
    // Left panel highlighting - always do this when quotes change
    if (leftPanelRef.current && selectedQuotes && selectedQuotes.length > 0) {
      highlightTextInScope(document, leftPanelRef.current, selectedQuotes)
    }

    // Iframe highlighting - only when iframe is loaded
    if (isIframeLoaded && selectedQuotes && selectedQuotes.length > 0) {
      handleQuotesChange(selectedQuotes)
    }
  }, [selectedQuotes, isIframeLoaded, handleQuotesChange])

  const handleEvaluate = (propertyId: string, action: 'accept' | 'reject') => {
    setEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      // Map accept to true, reject to false
      const targetValue = action === 'accept'

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(propertyId)
      } else {
        // Set new value
        newMap.set(propertyId, targetValue)
      }
      return newMap
    })
  }

  // Unified hover handler for all property types
  const handlePropertyHover = (property: Property) => {
    // Only update quotes (which triggers highlighting) if we're viewing this property's archived page
    if (
      property.archived_page &&
      selectedArchivedPage?.id === property.archived_page.id &&
      property.supporting_quotes &&
      property.supporting_quotes.length > 0
    ) {
      setSelectedQuotes(property.supporting_quotes)
    }
  }

  const handleSubmit = async () => {
    // If no evaluations, just skip to the next politician (doesn't count toward session)
    if (evaluations.size === 0) {
      skipPolitician()
      return
    }

    setIsSubmitting(true)

    const evaluationItems: EvaluationItem[] = Array.from(evaluations.entries()).map(
      ([id, isAccepted]) => ({
        id,
        is_accepted: isAccepted,
      }),
    )

    try {
      // Submit evaluation - context handles all errors, incrementing, advancing, and navigation
      await submitEvaluation(evaluationItems)

      // Clear evaluations state only after successful submission
      setEvaluations(new Map())
    } catch (error) {
      // Error already handled by context - just preserve evaluation state
      console.error('Submission failed:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="grid grid-cols-[46rem_1fr] bg-gray-50 min-h-0">
      {/* Left panel - Evaluation interface */}
      <div className="shadow-lg grid grid-rows-[1fr_auto] min-h-0">
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
                  {politician.name}{' '}
                  <span className="text-gray-500 font-normal">({politician.wikidata_id})</span>
                </a>
              </h1>
            ) : (
              <h1 className="text-2xl font-bold text-gray-900 mb-2">{politician.name}</h1>
            )}
          </div>

          <PropertiesEvaluation
            properties={politician.properties}
            evaluations={evaluations}
            onAction={handleEvaluate}
            onShowArchived={(property) => {
              if (property.archived_page) {
                setSelectedArchivedPage(property.archived_page)
                setSelectedQuotes(property.supporting_quotes || null)
              }
            }}
            onHover={handlePropertyHover}
            activeArchivedPageId={selectedArchivedPage?.id || null}
          />
        </div>

        {/* Fixed button at bottom */}
        <div className="p-6 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <div className="text-base text-gray-900">
              Progress:{' '}
              <strong>
                {completedCount} / {sessionGoal}
              </strong>{' '}
              politicians evaluated
            </div>
            <Button onClick={handleSubmit} disabled={isSubmitting} className="px-6 py-3">
              {isSubmitting
                ? 'Submitting...'
                : evaluations.size === 0
                  ? 'Skip Politician'
                  : 'Submit Evaluations & Next'}
            </Button>
          </div>
        </div>
      </div>

      {/* Right panel - Archived page viewer */}
      <div className="bg-gray-50 border-l border-gray-200 overflow-hidden min-h-0">
        {selectedArchivedPage ? (
          <iframe
            ref={iframeRef}
            src={`/api/archived-pages/${selectedArchivedPage.id}/html`}
            className="w-full h-full border-0"
            title="Archived Page"
            sandbox="allow-scripts allow-same-origin"
            onLoad={() => {
              archivedPageCache.markPageAsLoaded(selectedArchivedPage.id)
              handleIframeLoad()
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p className="text-lg mb-2">📄</p>
              <p>Click &ldquo;View&rdquo; on any item to see the source page</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
