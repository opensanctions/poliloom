'use client'

import { useState, useMemo, useRef, useEffect, useCallback, ReactNode } from 'react'
import {
  SourceResponse,
  Property,
  PropertyActionItem,
  CreatePropertyItem,
  PropertyReference,
} from '@/types'
import { actionToEvaluation, applyAction, createPropertyFromAction } from '@/lib/evaluation'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { PropertiesEvaluation } from './PropertiesEvaluation'
import { PoliticianHeader } from './PoliticianHeader'
import { ArchivedPageViewer } from './ArchivedPageViewer'

interface SourceEvaluationViewProps {
  source: SourceResponse
  footer: (actionsByPolitician: Map<string, PropertyActionItem[]>) => ReactNode
  archivedPagesApiPath?: string
}

export function SourceEvaluationView({
  source,
  footer,
  archivedPagesApiPath = '/api/archived-pages',
}: SourceEvaluationViewProps) {
  const [actionsByPolitician, setActionsByPolitician] = useState<Map<string, PropertyActionItem[]>>(
    () => {
      const map = new Map<string, PropertyActionItem[]>()
      for (const politician of source.politicians) {
        map.set(politician.wikidata_id!, [])
      }
      return map
    },
  )

  const displayPropertiesByPolitician = useMemo(() => {
    const result = new Map<string, Property[]>()
    for (const politician of source.politicians) {
      const qid = politician.wikidata_id!
      const actions = actionsByPolitician.get(qid) || []
      const originals = politician.properties.map((p) => ({
        ...p,
        evaluation: actionToEvaluation(actions, p.id!),
      }))
      const added = actions
        .filter((a): a is CreatePropertyItem => a.action === 'create')
        .map((a) => createPropertyFromAction(a))
      result.set(qid, [...originals, ...added])
    }
    return result
  }, [source.politicians, actionsByPolitician])

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

  const handleAction = (
    politicianQid: string,
    id: string,
    action: 'accept' | 'reject' | 'remove',
  ) => {
    setActionsByPolitician((prev) => {
      const next = new Map(prev)
      const actions = next.get(politicianQid) || []
      next.set(politicianQid, applyAction(actions, id, action))
      return next
    })
  }

  const handleAddProperty = (politicianQid: string, item: CreatePropertyItem) => {
    setActionsByPolitician((prev) => {
      const next = new Map(prev)
      const actions = next.get(politicianQid) || []
      next.set(politicianQid, [...actions, item])
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
          const properties = displayPropertiesByPolitician.get(qid) || []

          return (
            <div key={qid} className="mb-8">
              <div className="mb-6">
                <PoliticianHeader name={politician.name} wikidataId={qid} />
              </div>

              <PropertiesEvaluation
                properties={properties}
                onAction={(id, action) => handleAction(qid, id, action)}
                onShowArchived={handleShowArchived}
                onHover={handlePropertyHover}
                activeArchivedPageId={source.archived_page.id}
                onAddProperty={(item) => handleAddProperty(qid, item)}
              />
            </div>
          )
        })}
      </div>

      <div className="p-6 border-t border-border">{footer(actionsByPolitician)}</div>
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
