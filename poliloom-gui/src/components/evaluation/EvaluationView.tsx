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
import { AddEntityPropertyForm } from './AddEntityPropertyForm'
import { PoliticianHeader } from './PoliticianHeader'
import { SourceViewer } from './SourceViewer'
import { SourcesSection } from './SourcesSection'

export interface SourceSelection {
  source: SourceResponse
  quotes: string[] | null
}

export function findInitialSelection(
  politician: Politician,
  languageQids: string[],
): SourceSelection | null {
  if (languageQids.length > 0) {
    const langSet = new Set(languageQids)
    const prop = politician.properties.find(
      (p) =>
        !p.statement_id &&
        p.sources.length > 0 &&
        p.sources[0].source &&
        p.sources[0].source.language_qids.some((qid) => langSet.has(qid)),
    )
    if (prop) {
      const ref = prop.sources[0]
      return { source: ref.source, quotes: ref.supporting_quotes ?? null }
    }
  }

  const prop = politician.properties.find((p) => p.sources.length > 0 && !p.statement_id)
  if (prop) {
    const ref = prop.sources[0]
    if (ref.source) return { source: ref.source, quotes: ref.supporting_quotes ?? null }
  }
  return null
}

export function findSelectionForSource(
  politician: Politician,
  sourceId: string,
): SourceSelection | null {
  const source = politician.sources.find((s) => s.id === sourceId)
  if (!source) return null

  for (const prop of politician.properties) {
    const ref = prop.sources.find((r) => r.source.id === sourceId)
    if (ref) {
      return { source, quotes: ref.supporting_quotes ?? null }
    }
  }

  return { source, quotes: null }
}

export interface FooterContext {
  actions: PropertyActionItem[]
  isSubmitting: boolean
  submit: () => void
}

interface EvaluationViewProps {
  politician: Politician
  selection: SourceSelection | null
  onSelectionChange: (selection: SourceSelection | null) => void
  onSubmit?: (actions: PropertyActionItem[]) => Promise<void>
  footer: (context: FooterContext) => ReactNode
  sourcesApiPath?: string
  onNameChange?: (name: string) => void
  onAddSource?: (url: string) => Promise<void>
  isAdvancedMode?: boolean
  entitySearches?: Record<EntityPropertyType, SearchFn>
}

export function EvaluationView({
  politician,
  selection,
  onSelectionChange,
  onSubmit,
  footer,
  sourcesApiPath = '/api/sources',
  onNameChange,
  onAddSource,
  isAdvancedMode = false,
  entitySearches,
}: EvaluationViewProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [actions, setActions] = useState<PropertyActionItem[]>([])

  const displayProperties = useMemo<Property[]>(() => {
    const originals = politician.properties.map((p) => ({
      ...p,
      evaluation: actionToEvaluation(actions, p.id!),
    }))
    const added = actions
      .filter((a): a is CreatePropertyItem => a.action === 'create')
      .map((a) => createPropertyFromAction(a))
    return [...originals, ...added]
  }, [politician, actions])

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const propertiesRef = useRef<HTMLDivElement | null>(null)
  const quotes = selection?.quotes ?? null
  const { isIframeLoaded, handleIframeLoad, highlightText } = useIframeAutoHighlight(
    iframeRef,
    quotes,
  )

  useEffect(() => {
    if (propertiesRef.current) {
      highlightTextInScope(document, propertiesRef.current, quotes ?? [])
    }

    if (isIframeLoaded) {
      highlightText(quotes ?? [])
    }
  }, [quotes, isIframeLoaded, highlightText])

  const handleAction = (id: string, action: 'accept' | 'reject') => {
    setActions((prev) => applyAction(prev, id, action))
  }

  const submit = useCallback(async () => {
    if (!onSubmit) return
    setIsSubmitting(true)
    try {
      await onSubmit(actions)
      setActions([])
    } catch (error) {
      console.error('Submission failed:', error)
      alert(
        error instanceof Error ? error.message : 'Error submitting evaluations. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }, [onSubmit, actions])

  const handleViewSource = useCallback(
    (source: SourceResponse, quotes?: string[]) => {
      onSelectionChange({ source, quotes: quotes ?? null })
    },
    [onSelectionChange],
  )

  const handlePropertyHover = (property: Property) => {
    if (!selection) return
    const matchingRef = property.sources.find((s) => selection.source.id === s.source.id)
    if (!matchingRef?.supporting_quotes?.length) return
    onSelectionChange({ ...selection, quotes: matchingRef.supporting_quotes })
  }

  const activeSourceId = selection?.source.id ?? null

  const [addingSection, setAddingSection] = useState<SectionType | null>(null)

  const handleAdd = (item: CreatePropertyItem) => {
    setActions((prev) => [...prev, item])
    setAddingSection(null)
  }

  function renderAddForm(sectionType: SectionType) {
    const onCancel = () => setAddingSection(null)
    switch (sectionType) {
      case 'date':
        return <AddDatePropertyForm onAdd={handleAdd} onCancel={onCancel} />
      case PropertyType.P39:
      case PropertyType.P19:
      case PropertyType.P27:
        return (
          <AddEntityPropertyForm
            type={sectionType}
            onAdd={handleAdd}
            onCancel={onCancel}
            onSearch={entitySearches?.[sectionType]}
          />
        )
    }
  }

  const sections = groupPropertiesIntoSections(displayProperties, {
    showEmptySections: isAdvancedMode,
  })

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6" ref={propertiesRef}>
        <div className="flex flex-col gap-8">
          <PoliticianHeader
            name={politician.name}
            wikidataId={politician.wikidata_id ?? undefined}
            onNameChange={onNameChange}
          />

          <SourcesSection
            sources={politician.sources}
            activeSourceId={activeSourceId}
            onViewSource={handleViewSource}
            onAddSource={onAddSource && politician.wikidata_id ? onAddSource : undefined}
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
                            onAction={handleAction}
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
                    renderAddForm(section.sectionType)
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
      </div>

      <div className="p-6 border-t border-border">{footer({ actions, isSubmitting, submit })}</div>
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
