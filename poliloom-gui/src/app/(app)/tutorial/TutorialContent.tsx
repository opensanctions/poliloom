'use client'

import { useState, Fragment } from 'react'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import {
  EvaluationView,
  FooterContext,
  SourceSelection,
  findInitialSelection,
} from '@/components/evaluation/EvaluationView'
import { PoliticianHeader } from '@/components/evaluation/PoliticianHeader'
import { SourceViewer } from '@/components/evaluation/SourceViewer'
import { GroupTitle } from '@/components/evaluation/GroupTitle'
import { StatementItemView } from '@/components/evaluation/StatementItemView'
import { SourcesSection } from '@/components/evaluation/SourcesSection'
import { TutorialActions } from './_components/TutorialActions'
import { TutorialFooter } from './_components/TutorialFooter'
import { SuccessFeedback } from './_components/SuccessFeedback'
import { ErrorFeedback } from './_components/ErrorFeedback'
import { useSettings } from '@/contexts/SettingsContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { useUserLanguageCodes } from '@/hooks/useUserLanguageCodes'
import { best_label } from '@/lib/labels'
import {
  groupStatementsIntoSections,
  type ReviewSubmitPayload,
  type StatementItem,
} from '@/lib/actions'
import {
  TutorialStep,
  TutorialReviewStep,
  tutorialReviewSteps,
  tutorialSources,
  extractedDataPolitician,
} from './tutorialData'
export { TutorialStep }

interface CheckResult {
  isCorrect: boolean
  mistakes: string[]
}

/** Validate the submitted decisions against the expected ones for the step. */
function checkStep(payload: ReviewSubmitPayload, stepData: TutorialReviewStep): CheckResult {
  const mistakes: string[] = []

  for (const action of stepData.politician.actions) {
    const expected = stepData.expectedDecisions[action.id]
    if (expected === undefined) continue
    const decision = payload.decisions.find((d) => d.id === action.id)?.is_accepted ?? null
    if (decision !== expected) mistakes.push(action.id)
  }

  return { isCorrect: mistakes.length === 0, mistakes }
}

function TutorialReviewStepView({
  reviewStep,
  onSubmit,
  footer,
}: {
  reviewStep: TutorialReviewStep
  onSubmit: (payload: ReviewSubmitPayload) => Promise<void>
  footer: (context: FooterContext) => React.ReactNode
}) {
  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSelection(reviewStep.politician, []),
  )
  const userLanguageCodes = useUserLanguageCodes()
  return (
    <EvaluationView
      politician={reviewStep.politician}
      userLanguageCodes={userLanguageCodes}
      selection={selection}
      onSelectionChange={setSelection}
      onSubmit={onSubmit}
      footer={footer}
      sourcesApiPath="/api/tutorial-pages"
    />
  )
}

// Step ranges
const BASIC_START = TutorialStep.Welcome
const BASIC_END = TutorialStep.BasicKeyTakeaways
const ADVANCED_START = TutorialStep.AdvancedWelcome
const ADVANCED_END = TutorialStep.AdvancedKeyTakeaways

export interface TutorialContentProps {
  initialStep?: TutorialStep // For testing - allows starting at any step
}

export function TutorialContent({ initialStep }: TutorialContentProps) {
  const { settings, patch } = useSettings()
  const hasCompletedBasicTutorial = settings?.basic_tutorial_completed ?? true
  const hasCompletedAdvancedTutorial = settings?.advanced_tutorial_completed ?? true
  const isAdvancedMode = settings?.advanced_mode ?? false
  const { nextHref, loading: nextLoading } = useNextPoliticianContext()
  const userLanguageCodes = useUserLanguageCodes()

  const startHref = !nextLoading ? nextHref : undefined

  const getStartingStep = (): TutorialStep => {
    if (initialStep !== undefined) return initialStep
    if (!hasCompletedBasicTutorial) return BASIC_START
    if (isAdvancedMode && !hasCompletedAdvancedTutorial) return ADVANCED_START
    return BASIC_START
  }

  const [step, setStep] = useState(getStartingStep)

  const [checkResult, setCheckResult] = useState<CheckResult | null>(null)

  const advance = () => {
    const nextStep = step + 1
    if (nextStep > BASIC_END && !hasCompletedBasicTutorial) {
      patch({ basic_tutorial_completed: true })
    }
    if (nextStep > ADVANCED_END && !hasCompletedAdvancedTutorial) {
      patch({ advanced_tutorial_completed: true })
    }
    setCheckResult(null)
    setStep(nextStep)
  }

  const isBasicComplete = step > BASIC_END
  const isAdvancedComplete = step > ADVANCED_END
  const shouldShowAdvanced = isAdvancedMode && !hasCompletedAdvancedTutorial
  const isComplete = (isBasicComplete && !shouldShowAdvanced) || isAdvancedComplete

  if (isComplete) {
    return (
      <CenteredCard emoji="🎉" title="Tutorial Complete!">
        <p className="mb-8">
          You&apos;re all set! You now have everything you need to start reviewing politician data.
        </p>
        <Button href={startHref} size="large" fullWidth disabled={!startHref}>
          Start Reviewing
        </Button>
      </CenteredCard>
    )
  }

  if (step === TutorialStep.Welcome) {
    return (
      <CenteredCard emoji="👋" title="Welcome to PoliLoom!">
        <p className="mb-8">
          You&apos;re about to help build accurate, open political data by verifying information
          extracted from official sources.
        </p>
        <TutorialActions skipHref={startHref} buttonText="Let's Go" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.WhyYourHelpMatters) {
    return (
      <CenteredCard emoji="🤖" title="Why Your Help Matters">
        <div className="mb-8 space-y-4">
          <p>
            We&apos;ll show you a politician, their source documents, and statements the AI proposed
            from those sources.
          </p>
          <p>
            Your role is to check whether what the AI proposed actually matches what&apos;s written
            in the source document.
          </p>
        </div>
        <TutorialActions skipHref={startHref} buttonText="Got It" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.SourceDocuments) {
    return (
      <TwoPanel
        left={
          <CenteredCard emoji="📄" title="Source Documents">
            <div className="mb-8 space-y-4">
              <p>
                On the right you&apos;ll see archived web pages from government portals, Wikipedia,
                and other official sources.
              </p>
              <p>We save copies so you can verify the data even if the original page changes.</p>
            </div>
            <TutorialActions skipHref={startHref} buttonText="Next" onNext={advance} />
          </CenteredCard>
        }
        right={<SourceViewer pageId="tutorial-page-1" apiBasePath="/api/tutorial-pages" />}
      />
    )
  }

  if (step === TutorialStep.LinkedSources) {
    return (
      <TwoPanel
        left={
          <div className="overflow-y-auto p-6 h-full flex flex-col gap-8">
            <PoliticianHeader
              name={best_label(
                extractedDataPolitician.terms,
                userLanguageCodes,
                extractedDataPolitician.wikidata_id ?? extractedDataPolitician.id,
              )}
              wikidataId={extractedDataPolitician.wikidata_id ?? undefined}
            />
            <SourcesSection
              sources={[tutorialSources.page1]}
              activeSourceId={null}
              onViewSource={() => {}}
            />
          </div>
        }
        right={
          <CenteredCard emoji="🔗" title="Linked Sources">
            <div className="mb-8 space-y-4">
              <p>
                On the left you&apos;ll see what sources we have for each politician. We find and
                archive these automatically.
              </p>
              <p>
                Each proposal you review cites the source it came from, so you always know where a
                piece of data originated.
              </p>
            </div>
            <TutorialActions skipHref={startHref} buttonText="Next" onNext={advance} />
          </CenteredCard>
        }
      />
    )
  }

  if (step === TutorialStep.ExtractedData) {
    const sections = groupStatementsIntoSections(
      extractedDataPolitician.statements,
      extractedDataPolitician.actions,
    )
    return (
      <TwoPanel
        left={
          <div className="overflow-y-auto p-6 h-full flex flex-col gap-8">
            <PoliticianHeader
              name={best_label(
                extractedDataPolitician.terms,
                userLanguageCodes,
                extractedDataPolitician.wikidata_id ?? extractedDataPolitician.id,
              )}
              wikidataId={extractedDataPolitician.wikidata_id ?? undefined}
            />
            <SourcesSection
              sources={extractedDataPolitician.sources}
              activeSourceId={null}
              onViewSource={() => {}}
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
                      >
                        <div className="space-y-3">
                          {group.items.map((item, index) => (
                            <Fragment key={statementItemKey(item)}>
                              {index > 0 && <hr className="border-border-muted my-3" />}
                              <StatementItemView
                                item={item}
                                decisions={{}}
                                onDecision={() => {}}
                                onViewSource={() => {}}
                                onHover={() => {}}
                                activeSourceId={null}
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
        }
        right={
          <CenteredCard emoji="🗂️" title="Statements & Proposals">
            <div className="mb-8 space-y-4">
              <p>
                Below the sources you&apos;ll see what Wikidata already states about the politician,
                and the changes the AI proposed from the documents.
              </p>
              <p>
                Each proposal includes the source text used as evidence, and a link to view the full
                document.
              </p>
            </div>
            <TutorialActions skipHref={startHref} buttonText="Next" onNext={advance} />
          </CenteredCard>
        }
      />
    )
  }

  if (step === TutorialStep.GiveItATry) {
    return (
      <CenteredCard emoji="🎯" title="Give It a Try">
        <p className="mb-8">
          Compare each proposal to the source. If it matches, accept it. If it doesn&apos;t, discard
          it.
        </p>
        <TutorialActions skipHref={startHref} buttonText="Let's do it" onNext={advance} />
      </CenteredCard>
    )
  }

  // Interactive review steps — all share the same structure
  const reviewStep = tutorialReviewSteps[step]
  if (reviewStep) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title={reviewStep.success.title}
          message={reviewStep.success.message}
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title={reviewStep.error.title}
          message={reviewStep.error.message}
          hint={reviewStep.error.hint}
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <TutorialReviewStepView
        key={reviewStep.politician.id}
        reviewStep={reviewStep}
        onSubmit={async (payload) => setCheckResult(checkStep(payload, reviewStep))}
        footer={({ decidedCount, submit }) => (
          <TutorialFooter
            skipHref={startHref}
            isComplete={decidedCount === reviewStep.politician.actions.length}
            onSubmit={submit}
            onBack={() => setStep(reviewStep.backStep)}
          />
        )}
      />
    )
  }

  if (step === TutorialStep.MultipleSources) {
    return (
      <CenteredCard emoji="📚" title="Multiple Sources">
        <p className="mb-8">
          Sometimes information comes from different source documents. Next, try switching between
          these to review all proposals.
        </p>
        <TutorialActions skipHref={startHref} buttonText="Let's do it" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.SpecificOverGeneric) {
    return (
      <CenteredCard emoji="🎯" title="Specific Over Generic">
        <p className="mb-8">
          Specific data is better than generic data. If a more specific version already exists,
          discard the generic proposal.
        </p>
        <TutorialActions skipHref={startHref} buttonText="Let's do it" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.BasicKeyTakeaways) {
    return (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            Accept proposals that match the source. Discard proposals that don&apos;t match or are
            less specific than what we already have.
          </p>
          <p>
            Not sure about something? That&apos;s completely fine — just skip it. You&apos;re never
            required to decide on every proposal.
          </p>
        </div>
        <TutorialActions skipHref={startHref} buttonText="Got It!" onNext={advance} />
      </CenteredCard>
    )
  }

  // ============ ADVANCED TUTORIAL STEPS ============
  if (step === TutorialStep.AdvancedWelcome) {
    return (
      <CenteredCard emoji="⚡" title="Advanced Mode Tutorial">
        <div className="mb-8 space-y-4">
          <p>
            Welcome to advanced mode! Here you&apos;ll also review proposed edits to statements
            Wikidata already has.
          </p>
          <p>
            Edits can make a value more precise, complete a missing timeframe, or add a reference —
            and you decide them the same way: accept the ones the source supports, discard the ones
            it doesn&apos;t.
          </p>
        </div>
        <TutorialActions skipHref={startHref} buttonText="Let's Advance" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.RefiningValues) {
    return (
      <CenteredCard emoji="🎯" title="Refining Values">
        <p className="mb-8">
          Sometimes a source pins down a value more precisely than Wikidata does — a full birth date
          instead of just a year. Next, decide whether such a refinement is supported.
        </p>
        <TutorialActions skipHref={startHref} buttonText="Let's do it" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.CompletingTimeframes) {
    return (
      <CenteredCard emoji="📅" title="Completing Timeframes">
        <div className="mb-8 space-y-4">
          <p>
            Political positions can gain a missing start date — or carry a wrong one. Proposed edits
            show you exactly what would change.
          </p>
          <p>Check each proposed timeframe against its evidence before deciding.</p>
        </div>
        <TutorialActions skipHref={startHref} buttonText="Let's do it" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.AddingReferences) {
    return (
      <CenteredCard emoji="📚" title="Adding References">
        <div className="mb-8 space-y-4">
          <p>Statements without sources can gain references from the documents we archive.</p>
          <p>
            But only accept a reference when its evidence truly backs the statement — quotes about
            something else don&apos;t count.
          </p>
        </div>
        <TutorialActions skipHref={startHref} buttonText="Let's do it" onNext={advance} />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.AdvancedKeyTakeaways) {
    return (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            Refine what&apos;s imprecise, complete what&apos;s missing — and always check the
            evidence before accepting an edit.
          </p>
          <p>
            When a quote doesn&apos;t actually support the statement, discard the proposal. Someone
            else can always pick it up later.
          </p>
        </div>
        <TutorialActions skipHref={startHref} buttonText="Got It!" onNext={advance} />
      </CenteredCard>
    )
  }
}

function statementItemKey(item: StatementItem): string {
  return item.statement ? item.statement.id : item.createAction.id
}
