'use client'

import { useState, useRef, useEffect, useCallback, ReactNode } from 'react'
import { SourceResponse, Property, PropertyWithEvaluation, PropertyReference } from '@/types'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { PropertiesEvaluation } from './PropertiesEvaluation'
import { PoliticianHeader } from './PoliticianHeader'
import { ArchivedPageViewer } from './ArchivedPageViewer'

interface SourceEvaluationViewProps {
  source: SourceResponse
  footer: (propertiesByPolitician: Map<string, PropertyWithEvaluation[]>) => ReactNode
  archivedPagesApiPath?: string
}

export function SourceEvaluationView({
  source,
  footer,
  archivedPagesApiPath = '/api/archived-pages',
}: SourceEvaluationViewProps) {
  // Flat properties array with politician QID tracked per property
  const [propertiesByPolitician, setPropertiesByPolitician] = useState<
    Map<string, PropertyWithEvaluation[]>
  >(() => {
    const map = new Map<string, PropertyWithEvaluation[]>()
    for (const politician of source.politicians) {
      map.set(
        politician.wikidata_id!,
        politician.properties.map((p) => ({ ...p })),
      )
    }
    return map
  })

  const [selectedQuotes, setSelectedQuotes] = useState<string[] | null>(null)

  // Refs and hooks for highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const propertiesRef = useRef<HTMLDivElement | null>(null)
  const { isIframeLoaded, handleIframeLoad, handleQuotesChange } = useIframeAutoHighlight(
    iframeRef,
    selectedQuotes,
  )

  // Update highlighting when supporting quotes change
  useEffect(() => {
    if (propertiesRef.current && selectedQuotes && selectedQuotes.length > 0) {
      highlightTextInScope(document, propertiesRef.current, selectedQuotes)
    }

    if (isIframeLoaded && selectedQuotes && selectedQuotes.length > 0) {
      handleQuotesChange(selectedQuotes)
    }
  }, [selectedQuotes, isIframeLoaded, handleQuotesChange])

  const handleEvaluate = (politicianQid: string, key: string, action: 'accept' | 'reject') => {
    setPropertiesByPolitician((prev) => {
      const next = new Map(prev)
      const properties = next.get(politicianQid)
      if (!properties) return prev

      // User-added properties (no id) are removed on reject
      const target = properties.find((p) => p.key === key)
      if (action === 'reject' && target && !target.id) {
        next.set(
          politicianQid,
          properties.filter((p) => p.key !== key),
        )
        return next
      }

      next.set(
        politicianQid,
        properties.map((p) => {
          if (p.key !== key) return p
          const targetValue = action === 'accept'
          return { ...p, evaluation: p.evaluation === targetValue ? undefined : targetValue }
        }),
      )
      return next
    })
  }

  const handleAddProperty = (politicianQid: string, prop: PropertyWithEvaluation) => {
    setPropertiesByPolitician((prev) => {
      const next = new Map(prev)
      const properties = next.get(politicianQid) || []
      next.set(politicianQid, [...properties, prop])
      return next
    })
  }

  const handleShowArchived = useCallback((ref: PropertyReference) => {
    setSelectedQuotes(ref.supporting_quotes || null)
  }, [])

  const handlePropertyHover = (property: Property) => {
    const matchingRef = property.sources.find((s) => source.archived_page.id === s.archived_page.id)
    if (matchingRef?.supporting_quotes && matchingRef.supporting_quotes.length > 0) {
      setSelectedQuotes(matchingRef.supporting_quotes)
    }
  }

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6" ref={propertiesRef}>
        {source.politicians.map((politician) => {
          const qid = politician.wikidata_id!
          const properties = propertiesByPolitician.get(qid) || []

          return (
            <div key={qid} className="mb-8">
              <div className="mb-6">
                <PoliticianHeader name={politician.name} wikidataId={qid} />
              </div>

              <PropertiesEvaluation
                properties={properties}
                onAction={(key, action) => handleEvaluate(qid, key, action)}
                onShowArchived={handleShowArchived}
                onHover={handlePropertyHover}
                activeArchivedPageId={source.archived_page.id}
                onAddProperty={(prop) => handleAddProperty(qid, prop)}
              />
            </div>
          )
        })}
      </div>

      <div className="p-6 border-t border-border">{footer(propertiesByPolitician)}</div>
    </div>
  )

  const rightPanel = (
    <ArchivedPageViewer
      pageId={source.archived_page.id}
      apiBasePath={archivedPagesApiPath}
      iframeRef={iframeRef}
      onLoad={handleIframeLoad}
    />
  )

  return <TwoPanel left={leftPanel} right={rightPanel} />
}
