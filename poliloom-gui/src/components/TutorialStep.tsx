'use client'

import { useState, useRef, useEffect, ReactNode } from 'react'
import { Button } from '@/components/Button'
import { Anchor } from '@/components/Anchor'
import { PropertiesEvaluation } from '@/components/PropertiesEvaluation'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { useArchivedPageCache } from '@/contexts/ArchivedPageContext'
import { Property, ArchivedPageResponse } from '@/types'

export function TutorialStep({
  properties,
  archivedPages,
  politician,
  showArchivedPage,
  showLeftExplanation,
  showRightExplanation,
  isInteractive,
  explanationContent,
  onNext,
}: {
  properties: Property[]
  archivedPages: Record<string, ArchivedPageResponse>
  politician: { name: string; wikidataId: string }
  showArchivedPage: boolean
  showLeftExplanation: boolean
  showRightExplanation: boolean
  isInteractive: boolean
  explanationContent: ReactNode
  onNext: () => void
}) {
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(new Map())
  const [selectedArchivedPage, setSelectedArchivedPage] = useState<ArchivedPageResponse | null>(
    () => {
      if (!showArchivedPage) return null
      const first = properties.find((p) => p.archived_page)
      return first?.archived_page || Object.values(archivedPages)[0] || null
    },
  )
  const [selectedQuotes, setSelectedQuotes] = useState<string[] | null>(() => {
    if (!showArchivedPage) return null
    const first = properties.find((p) => p.archived_page)
    return first?.supporting_quotes || null
  })

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const leftPanelRef = useRef<HTMLDivElement | null>(null)
  const archivedPageCache = useArchivedPageCache()
  const { isIframeLoaded, handleIframeLoad, handleQuotesChange } = useIframeAutoHighlight(
    iframeRef,
    selectedQuotes,
  )

  useEffect(() => {
    if (leftPanelRef.current && selectedQuotes && selectedQuotes.length > 0) {
      highlightTextInScope(document, leftPanelRef.current, selectedQuotes)
    }
    if (isIframeLoaded && selectedQuotes && selectedQuotes.length > 0) {
      handleQuotesChange(selectedQuotes)
    }
  }, [selectedQuotes, isIframeLoaded, handleQuotesChange])

  const handleEvaluate = (propertyId: string, action: 'accept' | 'reject') => {
    if (!isInteractive) return
    setEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      const targetValue = action === 'accept'
      if (currentValue === targetValue) {
        newMap.delete(propertyId)
      } else {
        newMap.set(propertyId, targetValue)
      }
      return newMap
    })
  }

  const handlePropertyHover = (property: Property) => {
    if (
      property.archived_page &&
      selectedArchivedPage?.id === property.archived_page.id &&
      property.supporting_quotes?.length
    ) {
      setSelectedQuotes(property.supporting_quotes)
    }
  }

  const hasEvaluations = evaluations.size > 0

  return (
    <div className="grid grid-cols-[46rem_1fr] bg-gray-50 min-h-0">
      <div className="shadow-lg grid grid-rows-[1fr_auto] min-h-0">
        <div ref={leftPanelRef} className="overflow-y-auto min-h-0 p-6">
          {showLeftExplanation ? (
            explanationContent
          ) : (
            <>
              <div className="mb-6">
                <div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>
                <h1 className="text-2xl font-bold text-gray-900 mb-2">
                  <a
                    href={`https://www.wikidata.org/wiki/${politician.wikidataId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                  >
                    {politician.name}{' '}
                    <span className="text-gray-500 font-normal">({politician.wikidataId})</span>
                  </a>
                </h1>
              </div>
              {properties.length > 0 && (
                <PropertiesEvaluation
                  properties={properties}
                  evaluations={evaluations}
                  onAction={isInteractive ? handleEvaluate : () => {}}
                  onShowArchived={(property) => {
                    if (property.archived_page && showArchivedPage) {
                      setSelectedArchivedPage(property.archived_page)
                      setSelectedQuotes(property.supporting_quotes || null)
                    }
                  }}
                  onHover={handlePropertyHover}
                  activeArchivedPageId={selectedArchivedPage?.id || null}
                />
              )}
            </>
          )}
        </div>

        <div className="p-6 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <Anchor href="/evaluate" className="text-gray-500 hover:text-gray-700 font-medium">
              Skip Tutorial
            </Anchor>
            <Button
              onClick={onNext}
              disabled={isInteractive && !hasEvaluations}
              className="px-6 py-3"
            >
              {isInteractive ? 'Continue' : 'Next'}
            </Button>
          </div>
        </div>
      </div>

      <div className="bg-gray-50 border-l border-gray-200 overflow-hidden min-h-0">
        {showRightExplanation ? (
          explanationContent
        ) : showArchivedPage && selectedArchivedPage ? (
          <iframe
            ref={iframeRef}
            src={`/api/tutorial-pages/${selectedArchivedPage.id}/html`}
            className="w-full h-full border-0"
            title="Archived Page"
            sandbox="allow-scripts allow-same-origin"
            onLoad={() => {
              archivedPageCache.markPageAsLoaded(selectedArchivedPage.id)
              handleIframeLoad()
            }}
          />
        ) : (
          explanationContent
        )}
      </div>
    </div>
  )
}
