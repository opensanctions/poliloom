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

interface SourceSelection {
  source: SourceResponse
  quotes: string[] | null
}

function findInitialSource(politicians: Politician[]): SourceSelection | null {
  for (const politician of politicians) {
    const sourceMap = new Map(politician.sources.map((s) => [s.id, s]))
    const prop = politician.properties.find((p) => p.sources.length > 0 && !p.statement_id)
    if (prop) {
      const source = sourceMap.get(prop.sources[0].source_id)
      if (source) return { source, quotes: prop.sources[0].supporting_quotes ?? null }
    }
  }
  return null
}

export interface FooterContext {
  actionsByPolitician: Map<string, PropertyActionItem[]>
  isSubmitting: boolean
  submit: () => void
}

interface EvaluationViewProps {
  politicians: Politician[]
  onSubmit?: (actionsByPolitician: Map<string, PropertyActionItem[]>) => Promise<void>
  footer: (context: FooterContext) => ReactNode
  sourcesApiPath?: string
  onNameChange?: (politicianId: string, name: string) => void
  onSourceAdded?: () => void
}

export function EvaluationView({
  politicians,
  onSubmit,
  footer,
  sourcesApiPath = '/api/sources',
  onNameChange,
  onSourceAdded,
}: EvaluationViewProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
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

  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSource(politicians),
  )

  // Refs and hooks for highlighting
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const propertiesRef = useRef<HTMLDivElement | null>(null)
  const quotes = selection?.quotes ?? null
  const { isIframeLoaded, handleIframeLoad, handleQuotesChange } = useIframeAutoHighlight(
    iframeRef,
    quotes,
  )

  // Update highlighting when supporting quotes change
  useEffect(() => {
    if (propertiesRef.current && quotes && quotes.length > 0) {
      highlightTextInScope(document, propertiesRef.current, quotes)
    }

    if (isIframeLoaded && quotes && quotes.length > 0) {
      handleQuotesChange(quotes)
    }
  }, [quotes, isIframeLoaded, handleQuotesChange])

  const handleAction = (politicianKey: string, id: string, action: 'accept' | 'reject') => {
    setActionsByPolitician((prev) => {
      const next = new Map(prev)
      const actions = next.get(politicianKey) || []
      next.set(politicianKey, applyAction(actions, id, action))
      return next
    })
  }

  const clearActions = useCallback(() => {
    setActionsByPolitician(() => {
      const map = new Map<string, PropertyActionItem[]>()
      for (const politician of politicians) {
        map.set(politician.id, [])
      }
      return map
    })
  }, [politicians])

  const submit = useCallback(async () => {
    if (!onSubmit) return
    setIsSubmitting(true)
    try {
      await onSubmit(actionsByPolitician)
      clearActions()
    } catch (error) {
      console.error('Submission failed:', error)
      alert(
        error instanceof Error ? error.message : 'Error submitting evaluations. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }, [onSubmit, actionsByPolitician, clearActions])

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
      if (source) setSelection({ source, quotes: quotes ?? null })
    },
    [sourceById],
  )

  // Unified hover handler for all property types
  const handlePropertyHover = (property: Property) => {
    setSelection((prev) => {
      if (!prev) return prev
      const matchingRef = property.sources.find((s) => prev.source.id === s.source_id)
      if (!matchingRef?.supporting_quotes?.length) return prev
      return { ...prev, quotes: matchingRef.supporting_quotes }
    })
  }

  const activeSourceId = selection?.source.id ?? null

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6" ref={propertiesRef}>
        {politicians.map((politician) => {
          const properties = displayPropertiesByPolitician.get(politician.id) || []

          return (
            <div key={politician.id} className="mb-8">
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
                sources={politician.sources}
                activeSourceId={activeSourceId}
                onViewSource={handleViewSource}
                politicianQid={politician.wikidata_id ?? undefined}
                onAddSource={onSourceAdded}
              />

              <PropertiesEvaluation
                properties={properties}
                onAction={(id, action) => handleAction(politician.id, id, action)}
                onViewSource={handleViewSource}
                onHover={handlePropertyHover}
                activeSourceId={activeSourceId}
                sourceById={sourceById}
                onAddProperty={(item) => handleAddProperty(politician.id, item)}
              />
            </div>
          )
        })}
      </div>

      <div className="p-6 border-t border-border">
        {footer({ actionsByPolitician, isSubmitting, submit })}
      </div>
    </div>
  )

  const rightPanel = selection ? (
    <SourceViewer
      pageId={selection.source.id}
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
