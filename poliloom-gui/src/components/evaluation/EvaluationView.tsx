'use client'

import { useState, useMemo, useRef, useEffect, useCallback, ReactNode, Fragment } from 'react'
import {
  Politician,
  Property,
  PropertyType,
  EntityPropertyType,
  PropertyActionItem,
  CreatePropertyItem,
  SourceResponse,
  SearchFn,
} from '@/types'
import {
  actionToEvaluation,
  applyAction,
  createPropertyFromAction,
  groupPropertiesIntoSections,
  getAddLabel,
  SectionType,
} from '@/lib/evaluation'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { Button } from '@/components/ui/Button'
import { GroupTitle } from './GroupTitle'
import { PropertyDisplay } from './PropertyDisplay'
import { AddDatePropertyForm } from './AddDatePropertyForm'
import { AddEntityPropertyForm, DEFAULT_ENTITY_SEARCHES } from './AddEntityPropertyForm'
import { PoliticianHeader } from './PoliticianHeader'
import { SourceViewer } from './SourceViewer'
import { SourcesSection } from './SourcesSection'

interface SourceSelection {
  source: SourceResponse
  quotes: string[] | null
}

function findInitialSource(politicians: Politician[]): SourceSelection | null {
  for (const politician of politicians) {
    const prop = politician.properties.find((p) => p.sources.length > 0 && !p.statement_id)
    if (prop) {
      const ref = prop.sources[0]
      if (ref.source) return { source: ref.source, quotes: ref.supporting_quotes ?? null }
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
  onAddSource?: (politicianQid: string, url: string) => Promise<void>
  isAdvancedMode?: boolean
  entitySearches?: Record<EntityPropertyType, SearchFn>
}

export function EvaluationView({
  politicians,
  onSubmit,
  footer,
  sourcesApiPath = '/api/sources',
  onNameChange,
  onAddSource,
  isAdvancedMode = false,
  entitySearches = DEFAULT_ENTITY_SEARCHES,
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

  const handleViewSource = useCallback((source: SourceResponse, quotes?: string[]) => {
    setSelection({ source, quotes: quotes ?? null })
  }, [])

  // Unified hover handler for all property types
  const handlePropertyHover = (property: Property) => {
    setSelection((prev) => {
      if (!prev) return prev
      const matchingRef = property.sources.find((s) => prev.source.id === s.source.id)
      if (!matchingRef?.supporting_quotes?.length) return prev
      return { ...prev, quotes: matchingRef.supporting_quotes }
    })
  }

  const activeSourceId = selection?.source.id ?? null

  // --- Add property form state (advanced mode) ---
  const [addingSection, setAddingSection] = useState<SectionType | null>(null)

  const handleAdd = (politicianKey: string, item: CreatePropertyItem) => {
    handleAddProperty(politicianKey, item)
    setAddingSection(null)
  }

  function renderAddForm(sectionType: SectionType, politicianKey: string) {
    const onAdd = (item: CreatePropertyItem) => handleAdd(politicianKey, item)
    const onCancel = () => setAddingSection(null)
    switch (sectionType) {
      case 'date':
        return <AddDatePropertyForm onAdd={onAdd} onCancel={onCancel} />
      case PropertyType.P39:
      case PropertyType.P19:
      case PropertyType.P27:
        return (
          <AddEntityPropertyForm
            type={sectionType}
            onAdd={onAdd}
            onCancel={onCancel}
            onSearch={entitySearches[sectionType]}
          />
        )
    }
  }

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6" ref={propertiesRef}>
        {politicians.map((politician) => {
          const properties = displayPropertiesByPolitician.get(politician.id) || []
          const sections = groupPropertiesIntoSections(properties, {
            showEmptySections: isAdvancedMode,
          })

          return (
            <div key={politician.id} className="flex flex-col gap-8">
              <PoliticianHeader
                name={politician.name}
                wikidataId={politician.wikidata_id ?? undefined}
                onNameChange={
                  onNameChange ? (name) => onNameChange(politician.id, name) : undefined
                }
              />

              <SourcesSection
                sources={politician.sources}
                activeSourceId={activeSourceId}
                onViewSource={handleViewSource}
                onAddSource={
                  onAddSource && politician.wikidata_id
                    ? (url) => onAddSource(politician.wikidata_id!, url)
                    : undefined
                }
              />

              {sections.map((section) => (
                <div key={section.title}>
                  <h2 className="text-xl font-semibold text-foreground mb-4">{section.title}</h2>
                  <div className="space-y-4">
                    {section.groups.map((group) => (
                      <HeaderedBox
                        key={group.key}
                        title={<GroupTitle property={group.properties[0]} />}
                        onHover={() => {
                          const firstWithSource = group.properties.find(
                            (p) => p.sources.length > 0 && !p.statement_id,
                          )
                          if (firstWithSource) {
                            handlePropertyHover(firstWithSource)
                          }
                        }}
                      >
                        <div className="space-y-3">
                          {group.properties.map((property, index) => (
                            <Fragment key={property.id}>
                              {index > 0 && <hr className="border-border-muted my-3" />}
                              <PropertyDisplay
                                property={property}
                                onAction={(id, action) => handleAction(politician.id, id, action)}
                                onViewSource={handleViewSource}
                                onHover={handlePropertyHover}
                                activeSourceId={activeSourceId}
                                shouldAutoOpen={true}
                                showExistingStatementActions={isAdvancedMode}
                              />
                            </Fragment>
                          ))}
                        </div>
                      </HeaderedBox>
                    ))}
                  </div>
                  {isAdvancedMode && (
                    <div className="mt-4">
                      {addingSection === section.sectionType ? (
                        renderAddForm(section.sectionType, politician.id)
                      ) : (
                        <Button
                          variant="secondary"
                          size="small"
                          onClick={() => setAddingSection(section.sectionType)}
                        >
                          {getAddLabel(section.sectionType)}
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              ))}
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
