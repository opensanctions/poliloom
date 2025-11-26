'use client'

import { useState, useRef, useEffect, ReactNode } from 'react'
import { Politician, Property, ArchivedPageResponse } from '@/types'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { PropertiesEvaluation } from './PropertiesEvaluation'
import { PoliticianHeader } from './PoliticianHeader'
import { ArchivedPageViewer } from './ArchivedPageViewer'

// Helper function to find first new property with archived page
// Only new properties (without statement_id) show the View button
function findFirstPropertyWithArchive(properties: Property[]) {
  return properties.find((p) => p.archived_page && !p.statement_id)
}

interface PoliticianEvaluationViewProps {
  politician: Politician
  header?: ReactNode
  footer: (evaluations: Map<string, boolean>) => ReactNode
  archivedPagesApiPath?: string
}

export function PoliticianEvaluationView({
  politician,
  header,
  footer,
  archivedPagesApiPath = '/api/archived-pages',
}: PoliticianEvaluationViewProps) {
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(new Map())

  // Initialize with first archived page found (component should be keyed by politician.id)
  const [selectedArchivedPage, setSelectedArchivedPage] = useState<ArchivedPageResponse | null>(
    () => {
      const first = findFirstPropertyWithArchive(politician.properties)
      return first?.archived_page ?? null
    },
  )
  const [selectedQuotes, setSelectedQuotes] = useState<string[] | null>(() => {
    const first = findFirstPropertyWithArchive(politician.properties)
    return first?.supporting_quotes ?? null
  })

  // Refs and hooks for highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const propertiesRef = useRef<HTMLDivElement | null>(null)
  const { isIframeLoaded, handleIframeLoad, handleQuotesChange } = useIframeAutoHighlight(
    iframeRef,
    selectedQuotes,
  )

  // Update highlighting when supporting quotes change
  useEffect(() => {
    // Properties panel highlighting - always do this when quotes change
    if (propertiesRef.current && selectedQuotes && selectedQuotes.length > 0) {
      highlightTextInScope(document, propertiesRef.current, selectedQuotes)
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
      const targetValue = action === 'accept'

      if (currentValue === targetValue) {
        newMap.delete(propertyId)
      } else {
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

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6">
        <div className="mb-6">
          {header}
          <PoliticianHeader
            name={politician.name}
            wikidataId={politician.wikidata_id ?? undefined}
          />
        </div>

        <div ref={propertiesRef}>
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
      </div>

      <div className="p-6 border-t border-gray-200">{footer(evaluations)}</div>
    </div>
  )

  const rightPanel = selectedArchivedPage ? (
    <ArchivedPageViewer
      pageId={selectedArchivedPage.id}
      apiBasePath={archivedPagesApiPath}
      iframeRef={iframeRef}
      onLoad={handleIframeLoad}
    />
  ) : (
    <div className="flex items-center justify-center h-full text-gray-500">
      <div className="text-center">
        <p className="text-lg mb-2">📄</p>
        <p>Click &ldquo;View&rdquo; on any item to see the source page</p>
      </div>
    </div>
  )

  return <TwoPanel left={leftPanel} right={rightPanel} />
}
