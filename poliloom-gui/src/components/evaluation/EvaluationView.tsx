'use client'

import { useState, useMemo, useRef, useEffect, useCallback, ReactNode } from 'react'
import {
  Politician,
  Property,
  PropertyActionItem,
  CreatePropertyItem,
  SourceResponse,
} from '@/types'
import { actionToEvaluation, applyAction, createPropertyFromAction } from '@/lib/evaluation'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { PropertiesEvaluation } from './PropertiesEvaluation'
import { PoliticianHeader } from './PoliticianHeader'
import { SourceViewer } from './SourceViewer'
import { SourcesList } from './SourcesList'

interface EvaluationViewProps {
  politicians: Politician[]
  footer: (actionsByPolitician: Map<string, PropertyActionItem[]>) => ReactNode
  sourcesApiPath?: string
  onNameChange?: (politicianId: string, name: string) => void
  onSourceAdded?: () => void
}

export function EvaluationView({
  politicians,
  footer,
  sourcesApiPath = '/api/sources',
  onNameChange,
  onSourceAdded,
}: EvaluationViewProps) {
  const [actionsByPolitician, setActionsByPolitician] = useState<Map<string, PropertyActionItem[]>>(
    () => {
      const map = new Map<string, PropertyActionItem[]>()
      for (const politician of politicians) {
        map.set(politician.id, [])
      }
      return map
    },
  )

  const displayPropertiesByPolitician = useMemo(() => {
    const result = new Map<string, Property[]>()
    for (const politician of politicians) {
      const key = politician.id
      const actions = actionsByPolitician.get(key) || []
      const originals = politician.properties.map((p) => ({
        ...p,
        evaluation: actionToEvaluation(actions, p.id!),
      }))
      const added = actions
        .filter((a): a is CreatePropertyItem => a.action === 'create')
        .map((a) => createPropertyFromAction(a))
      result.set(key, [...originals, ...added])
    }
    return result
  }, [politicians, actionsByPolitician])

  // Initial selection is handled by PropertiesEvaluation calling onShowSource on mount
  const [selectedSource, setSelectedSource] = useState<SourceResponse | null>(null)
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

  const handleAction = (politicianKey: string, id: string, action: 'accept' | 'reject') => {
    setActionsByPolitician((prev) => {
      const next = new Map(prev)
      const actions = next.get(politicianKey) || []
      next.set(politicianKey, applyAction(actions, id, action))
      return next
    })
  }

  const handleAddProperty = (politicianKey: string, item: CreatePropertyItem) => {
    setActionsByPolitician((prev) => {
      const next = new Map(prev)
      const actions = next.get(politicianKey) || []
      next.set(politicianKey, [...actions, item])
      return next
    })
  }

  // Build a lookup map of all sources by ID across all politicians
  const sourceById = useMemo(() => {
    const map = new Map<string, SourceResponse>()
    for (const politician of politicians) {
      for (const page of politician.sources || []) {
        map.set(page.id, page)
      }
    }
    return map
  }, [politicians])

  const handleViewSource = useCallback(
    (sourceId: string, quotes?: string[]) => {
      const source = sourceById.get(sourceId)
      if (source) setSelectedSource(source)
      setSelectedQuotes(quotes || null)
    },
    [sourceById],
  )

  // Unified hover handler for all property types
  const handlePropertyHover = (property: Property) => {
    const matchingRef = property.sources.find((s) => selectedSource?.id === s.source_id)
    if (matchingRef?.supporting_quotes && matchingRef.supporting_quotes.length > 0) {
      setSelectedQuotes(matchingRef.supporting_quotes)
    }
  }

  // Collect unique sources across all politicians' property sources + top-level
  const sourcesByPolitician = useMemo(() => {
    const result = new Map<string, SourceResponse[]>()
    for (const politician of politicians) {
      const seen = new Map<string, SourceResponse>()
      // Top-level sources linked directly to politician
      for (const page of politician.sources || []) {
        if (!seen.has(page.id)) {
          seen.set(page.id, page)
        }
      }
      // Pages from property references (look up from top-level list)
      for (const prop of politician.properties) {
        for (const ref of prop.sources) {
          if (!seen.has(ref.source_id)) {
            const page = sourceById.get(ref.source_id)
            if (page) {
              seen.set(ref.source_id, page)
            }
          }
        }
      }
      result.set(politician.id, Array.from(seen.values()))
    }
    return result
  }, [politicians, sourceById])

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6" ref={propertiesRef}>
        {politicians.map((politician) => {
          const key = politician.id
          const properties = displayPropertiesByPolitician.get(key) || []
          const sources = sourcesByPolitician.get(key) || []

          return (
            <div key={key} className="mb-8">
              <div className="mb-6">
                <PoliticianHeader
                  name={politician.name}
                  wikidataId={politician.wikidata_id ?? undefined}
                  onNameChange={
                    onNameChange ? (name) => onNameChange(politician.id, name) : undefined
                  }
                />
              </div>

              <SourcesList
                sources={sources}
                activeSourceId={selectedSource?.id || null}
                onViewSource={handleViewSource}
                politicianQid={politician.wikidata_id ?? undefined}
                onAddSource={onSourceAdded}
              />

              <PropertiesEvaluation
                properties={properties}
                onAction={(id, action) => handleAction(key, id, action)}
                onViewSource={handleViewSource}
                onHover={handlePropertyHover}
                activeSourceId={selectedSource?.id || null}
                sourceById={sourceById}
                onAddProperty={(item) => handleAddProperty(key, item)}
              />
            </div>
          )
        })}
      </div>

      <div className="p-6 border-t border-border">{footer(actionsByPolitician)}</div>
    </div>
  )

  const rightPanel = selectedSource ? (
    <SourceViewer
      pageId={selectedSource.id}
      apiBasePath={sourcesApiPath}
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
