'use client'

import { useState, useMemo, useRef, useEffect, useCallback, ReactNode, Fragment } from 'react'
import {
  type Action,
  type Politician,
  type ReviewSubmitPayload,
  type SourceResponse,
} from '@/types'
import {
  buildSubmission,
  effectiveDecision,
  groupStatementsIntoSections,
  type LocalDecisions,
  type StatementItem,
} from '@/lib/actions'
import { best_label } from '@/lib/labels'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { GroupTitle } from './GroupTitle'
import { StatementItemView } from './StatementItemView'
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
  const withEvidence = politician.actions.filter((action) => action.evidence.length > 0)

  if (languageQids.length > 0) {
    const langSet = new Set(languageQids)
    const matching = withEvidence.find((action) =>
      action.evidence.some((evidence) =>
        evidence.source.language_qids.some((qid) => langSet.has(qid)),
      ),
    )
    if (matching) {
      const evidence = matching.evidence.find((e) =>
        e.source.language_qids.some((qid) => langSet.has(qid)),
      )!
      return { source: evidence.source, quotes: evidence.supporting_quotes ?? null }
    }
  }

  const first = withEvidence[0]
  if (first) {
    return {
      source: first.evidence[0].source,
      quotes: first.evidence[0].supporting_quotes ?? null,
    }
  }
  return null
}

export function findSelectionForSource(
  politician: Politician,
  sourceId: string,
): SourceSelection | null {
  const source = politician.sources.find((s) => s.id === sourceId)
  if (!source) return null

  for (const action of politician.actions) {
    const evidence = action.evidence.find((e) => e.source.id === sourceId)
    if (evidence) {
      return { source, quotes: evidence.supporting_quotes ?? null }
    }
  }

  return { source, quotes: null }
}

export interface FooterContext {
  decidedCount: number
  isSubmitting: boolean
  submit: () => void
}

interface EvaluationViewProps {
  politician: Politician
  userLanguageCodes: string[]
  selection: SourceSelection | null
  onSelectionChange: (selection: SourceSelection | null) => void
  onSubmit?: (payload: ReviewSubmitPayload) => Promise<void>
  footer: (context: FooterContext) => ReactNode
  sourcesApiPath?: string
  onAddSource?: (url: string) => Promise<void>
}

export function EvaluationView({
  politician,
  userLanguageCodes,
  selection,
  onSelectionChange,
  onSubmit,
  footer,
  sourcesApiPath = '/api/sources',
  onAddSource,
}: EvaluationViewProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [decisions, setDecisions] = useState<LocalDecisions>({})

  const sections = useMemo(
    () => groupStatementsIntoSections(politician.statements, politician.actions),
    [politician.statements, politician.actions],
  )

  const decidedCount = politician.actions.filter(
    (action) => effectiveDecision(action, decisions) !== null,
  ).length

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const statementsRef = useRef<HTMLDivElement | null>(null)
  const quotes = selection?.quotes ?? null
  const { isIframeLoaded, handleIframeLoad, highlightText } = useIframeAutoHighlight(
    iframeRef,
    quotes,
  )

  useEffect(() => {
    if (statementsRef.current) {
      highlightTextInScope(document, statementsRef.current, quotes ?? [])
    }

    if (isIframeLoaded) {
      highlightText(quotes ?? [])
    }
  }, [quotes, isIframeLoaded, highlightText])

  // Clicking the currently active choice returns the action to undecided (null).
  const handleDecision = useCallback((action: Action, isAccepted: boolean) => {
    setDecisions((prev) => ({
      ...prev,
      [action.id]: effectiveDecision(action, prev) === isAccepted ? null : isAccepted,
    }))
  }, [])

  const submit = useCallback(async () => {
    if (!onSubmit) return
    setIsSubmitting(true)
    try {
      await onSubmit(buildSubmission(politician.actions, decisions))
      setDecisions({})
    } catch (error) {
      console.error('Submission failed:', error)
      alert(
        error instanceof Error ? error.message : 'Error submitting decisions. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }, [onSubmit, politician.actions, decisions])

  const handleViewSource = useCallback(
    (source: SourceResponse, quotes?: string[]) => {
      onSelectionChange({ source, quotes: quotes ?? null })
    },
    [onSelectionChange],
  )

  const handleItemHover = (item: StatementItem) => {
    if (!selection) return
    const actions = item.createAction ? [item.createAction] : item.editActions
    const matching = actions
      .flatMap((action) => action.evidence)
      .find((evidence) => evidence.source.id === selection.source.id)
    if (!matching?.supporting_quotes?.length) return
    onSelectionChange({ ...selection, quotes: matching.supporting_quotes })
  }

  const activeSourceId = selection?.source.id ?? null

  const politicianName = best_label(
    politician.terms,
    userLanguageCodes,
    politician.wikidata_id ?? politician.id,
  )

  const leftPanel = (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="overflow-y-auto min-h-0 p-6" ref={statementsRef}>
        <div className="flex flex-col gap-8">
          <PoliticianHeader
            name={politicianName}
            wikidataId={politician.wikidata_id ?? undefined}
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
                {section.groups.map((group) => {
                  const first = group.items[0]
                  const terms =
                    first.statement?.entity_terms ?? first.createAction?.entity_terms ?? null
                  return (
                    <HeaderedBox
                      key={group.key}
                      title={
                        <GroupTitle
                          sectionType={section.sectionType}
                          groupKey={group.key}
                          terms={terms}
                          userLanguageCodes={userLanguageCodes}
                        />
                      }
                      onHover={() => handleItemHover(first)}
                    >
                      <div className="space-y-3">
                        {group.items.map((item, index) => (
                          <Fragment key={item.statement ? item.statement.id : item.createAction.id}>
                            {index > 0 && <hr className="border-border-muted my-3" />}
                            <StatementItemView
                              item={item}
                              decisions={decisions}
                              onDecision={handleDecision}
                              onViewSource={handleViewSource}
                              onHover={handleItemHover}
                              activeSourceId={activeSourceId}
                              userLanguageCodes={userLanguageCodes}
                            />
                          </Fragment>
                        ))}
                      </div>
                    </HeaderedBox>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-6 border-t border-border">
        {footer({ decidedCount, isSubmitting, submit })}
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
