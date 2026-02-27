'use client'

import { useState, useMemo, useRef, useEffect, useCallback, ReactNode } from 'react'
import {
  Politician,
  Property,
  PropertyActionItem,
  CreatePropertyItem,
  PropertyReference,
  ArchivedPageResponse,
} from '@/types'
import { actionToEvaluation, applyAction, createPropertyFromAction } from '@/lib/evaluation'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { PropertiesEvaluation } from './PropertiesEvaluation'
import { PoliticianHeader } from './PoliticianHeader'
import { ArchivedPageViewer } from './ArchivedPageViewer'

interface PoliticianEvaluationViewProps {
  politician: Politician
  footer: (actions: PropertyActionItem[]) => ReactNode
  archivedPagesApiPath?: string
}

export function PoliticianEvaluationView({
  politician,
  footer,
  archivedPagesApiPath = '/api/archived-pages',
}: PoliticianEvaluationViewProps) {
  const [actions, setActions] = useState<PropertyActionItem[]>([])

  const displayProperties: Property[] = useMemo(() => {
    const originals = politician.properties.map((p) => ({
      ...p,
      evaluation: actionToEvaluation(actions, p.id!),
    }))
    const added = actions
      .filter((a): a is CreatePropertyItem => a.action === 'create')
      .map((a) => createPropertyFromAction(a))
    return [...originals, ...added]
  }, [politician.properties, actions])

  // Initial selection is handled by PropertiesEvaluation calling onShowArchived on mount
  const [selectedArchivedPage, setSelectedArchivedPage] = useState<ArchivedPageResponse | null>(
    null,
  )
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
    // Properties panel highlighting - always do this when quotes change
    if (propertiesRef.current && selectedQuotes && selectedQuotes.length > 0) {
      highlightTextInScope(document, propertiesRef.current, selectedQuotes)
    }

    // Iframe highlighting - only when iframe is loaded
    if (isIframeLoaded && selectedQuotes && selectedQuotes.length > 0) {
      handleQuotesChange(selectedQuotes)
    }
  }, [selectedQuotes, isIframeLoaded, handleQuotesChange])

  const handleAction = (id: string, action: 'accept' | 'reject' | 'remove') => {
    setActions((prev) => applyAction(prev, id, action))
  }

  const handleAddProperty = (item: CreatePropertyItem) => {
    setActions((prev) => [...prev, item])
  }

  // Handler for showing archived page (used by View button and initial selection)
  const handleShowArchived = useCallback((ref: PropertyReference) => {
    setSelectedArchivedPage(ref.archived_page)
    setSelectedQuotes(ref.supporting_quotes || null)
  }, [])

  // Unified hover handler for all property types
  const handlePropertyHover = (property: Property) => {
    // Only update quotes (which triggers highlighting) if we're viewing this property's archived page
    const matchingRef = property.sources.find(
      (s) => selectedArchivedPage?.id === s.archived_page.id,
    )
    if (matchingRef?.supporting_quotes && matchingRef.supporting_quotes.length > 0) {
      setSelectedQuotes(matchingRef.supporting_quotes)
    }
  }

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6">
        <div className="mb-6">
          <PoliticianHeader
            name={politician.name}
            wikidataId={politician.wikidata_id ?? undefined}
          />
        </div>

        <div ref={propertiesRef}>
          <PropertiesEvaluation
            properties={displayProperties}
            onAction={handleAction}
            onShowArchived={handleShowArchived}
            onHover={handlePropertyHover}
            activeArchivedPageId={selectedArchivedPage?.id || null}
            onAddProperty={handleAddProperty}
          />
        </div>
      </div>

      <div className="p-6 border-t border-border">{footer(actions)}</div>
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
    <CenteredCard emoji="📄" title="Select a Source">
      <p>Click &ldquo;View&rdquo; on any item to see the source page</p>
    </CenteredCard>
  )

  return <TwoPanel left={leftPanel} right={rightPanel} />
}
