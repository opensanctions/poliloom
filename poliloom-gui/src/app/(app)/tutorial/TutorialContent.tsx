'use client'

import { useState, useEffect, Fragment } from 'react'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { EvaluationView } from '@/components/evaluation/EvaluationView'
import { PoliticianHeader } from '@/components/evaluation/PoliticianHeader'
import { SourceViewer } from '@/components/evaluation/SourceViewer'
import { GroupTitle } from '@/components/evaluation/GroupTitle'
import { PropertyDisplay } from '@/components/evaluation/PropertyDisplay'
import { SourcesSection } from '@/components/evaluation/SourcesSection'
import { TutorialActions } from './_components/TutorialActions'
import { TutorialFooter } from './_components/TutorialFooter'
import { SuccessFeedback } from './_components/SuccessFeedback'
import { ErrorFeedback } from './_components/ErrorFeedback'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { PropertyActionItem, CreatePropertyItem } from '@/types'
import { actionToEvaluation, groupPropertiesIntoSections } from '@/lib/evaluation'
import {
  TutorialStep,
  TutorialEvaluationStep,
  tutorialEvaluationSteps,
  tutorialSources,
  extractedDataPolitician,
} from './tutorialData'
export { TutorialStep }

interface EvaluationResult {
  isCorrect: boolean
  mistakes: string[]
}

/** Check whether the user has done enough to submit (required evaluations + creates). */
function isStepComplete(actions: PropertyActionItem[], stepData: TutorialEvaluationStep): boolean {
  const requiredProps = stepData.politician.properties.filter(
    (p) => p.expectedEvaluation !== undefined && (p.required ?? true),
  )
  const hasEvals = requiredProps.every((p) =>
    actions.some((a) => a.action !== 'create' && a.id === p.id),
  )
  const hasCreates =
    !stepData.expectedCreates ||
    stepData.expectedCreates.every((c) =>
      actions.some((a) => a.action === 'create' && a.type === c.type),
    )
  return hasEvals && hasCreates
}

/** Validate all actions against expected evaluations and creates. */
function checkStep(
  actions: PropertyActionItem[],
  stepData: TutorialEvaluationStep,
): EvaluationResult {
  const mistakes: string[] = []

  for (const prop of stepData.politician.properties) {
    if (prop.expectedEvaluation === undefined) continue
    const actual = actionToEvaluation(actions, prop.id)
    // No action on an expected-true property means "keep", which is correct
    if (prop.expectedEvaluation === true && actual === undefined) continue
    if (actual !== prop.expectedEvaluation) mistakes.push(prop.id)
  }

  if (stepData.expectedCreates) {
    for (const create of stepData.expectedCreates) {
      const action = actions.find(
        (a): a is CreatePropertyItem => a.action === 'create' && a.type === create.type,
      )
      if (!action) {
        mistakes.push('no-create')
      } else if (action.entity_id !== create.entity_id) {
        mistakes.push('wrong-entity')
      }
    }
  }

  return { isCorrect: mistakes.length === 0, mistakes }
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
  const {
    hasCompletedBasicTutorial,
    hasCompletedAdvancedTutorial,
    completeBasicTutorial,
    completeAdvancedTutorial,
  } = useUserProgress()
  const { isAdvancedMode } = useUserPreferences()
  const { startSession } = useEvaluationSession()
  const { nextHref, loading: nextLoading } = useNextPoliticianContext()

  const startHref = !nextLoading ? (nextHref ?? undefined) : undefined

  // Determine starting step based on completion status
  const getStartingStep = (): TutorialStep => {
    if (initialStep !== undefined) return initialStep
    if (!hasCompletedBasicTutorial) return BASIC_START
    if (isAdvancedMode && !hasCompletedAdvancedTutorial) return ADVANCED_START
    return BASIC_START
  }

  const [step, setStep] = useState(getStartingStep)

  // Single state for the result of the current interactive step's "Check Answers"
  const [checkResult, setCheckResult] = useState<EvaluationResult | null>(null)

  const advance = () => {
    setCheckResult(null)
    setStep((s) => s + 1)
  }

  // Handle tutorial completion
  useEffect(() => {
    // Complete basic tutorial when passing the last basic step
    if (step > BASIC_END && !hasCompletedBasicTutorial) {
      completeBasicTutorial()
    }
    // Complete advanced tutorial when passing the last advanced step
    if (step > ADVANCED_END) {
      completeAdvancedTutorial()
    }
  }, [step, hasCompletedBasicTutorial, completeBasicTutorial, completeAdvancedTutorial])

  // Determine what to show
  const isBasicComplete = step > BASIC_END
  const isAdvancedComplete = step > ADVANCED_END
  const shouldShowAdvanced = isAdvancedMode && !hasCompletedAdvancedTutorial

  // Show completion screen when:
  // - Basic is done AND (not in advanced mode OR advanced is already completed)
  // - OR advanced is done
  const isComplete = (isBasicComplete && !shouldShowAdvanced) || isAdvancedComplete

  // Completion screen
  if (isComplete) {
    return (
      <CenteredCard emoji="🎉" title="Tutorial Complete!">
        <p className="mb-8">
          You&apos;re all set! You now have everything you need to start verifying politician data.
        </p>
        <Button
          href={startHref}
          size="large"
          fullWidth
          disabled={!startHref}
          onClick={() => startSession()}
        >
          Start Evaluating
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
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's Go"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.WhyYourHelpMatters) {
    return (
      <CenteredCard emoji="🤖" title="Why Your Help Matters">
        <div className="mb-8 space-y-4">
          <p>
            We&apos;ll show you a politician, their source documents, and data that AI extracted
            from those sources.
          </p>
          <p>
            Your role is to check whether what the AI extracted actually matches what&apos;s written
            in the source document.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It"
          onNext={advance}
        />
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
            <TutorialActions
              skipHref={startHref}
              onSkip={() => startSession()}
              buttonText="Next"
              onNext={advance}
            />
          </CenteredCard>
        }
        right={<SourceViewer pageId="tutorial-page-1" apiBasePath="/api/tutorial-pages" />}
      />
    )
  }

  if (step === TutorialStep.SourcesAndAddSource) {
    return (
      <TwoPanel
        left={
          <div className="overflow-y-auto p-6 h-full flex flex-col gap-8">
            <PoliticianHeader
              name={extractedDataPolitician.name}
              wikidataId={extractedDataPolitician.wikidata_id ?? undefined}
            />
            <SourcesSection
              sources={[tutorialSources.page1]}
              activeSourceId={null}
              onViewSource={() => {}}
              onAddSource={async () => {}}
            />
          </div>
        }
        right={
          <CenteredCard emoji="🔗" title="Linked Sources">
            <div className="mb-8 space-y-4">
              <p>
                On the left you&apos;ll see what sources we have for each politician. We find and
                archive these automatically, but you can add your own too.
              </p>
              <p>
                Just paste a URL — we&apos;ll do our best to archive the page and extract data from
                it.
              </p>
            </div>
            <TutorialActions
              skipHref={startHref}
              onSkip={() => startSession()}
              buttonText="Next"
              onNext={advance}
            />
          </CenteredCard>
        }
      />
    )
  }

  if (step === TutorialStep.ExtractedData) {
    return (
      <TwoPanel
        left={
          <div className="overflow-y-auto p-6 h-full flex flex-col gap-8">
            <PoliticianHeader
              name={extractedDataPolitician.name}
              wikidataId={extractedDataPolitician.wikidata_id ?? undefined}
            />
            <SourcesSection
              sources={extractedDataPolitician.sources}
              activeSourceId={null}
              onViewSource={() => {}}
              onAddSource={async () => {}}
            />
            {groupPropertiesIntoSections(extractedDataPolitician.properties).map((section) => (
              <div key={section.title}>
                <h2 className="text-xl font-semibold text-foreground mb-4">{section.title}</h2>
                <div className="space-y-4">
                  {section.groups.map((group) => (
                    <HeaderedBox
                      key={group.key}
                      title={<GroupTitle property={group.properties[0]} />}
                    >
                      <div className="space-y-3">
                        {group.properties.map((property, index) => (
                          <Fragment key={property.id}>
                            {index > 0 && <hr className="border-border-muted my-3" />}
                            <PropertyDisplay
                              property={property}
                              onAction={() => {}}
                              onViewSource={() => {}}
                              onHover={() => {}}
                              activeSourceId={null}
                              shouldAutoOpen={true}
                            />
                          </Fragment>
                        ))}
                      </div>
                    </HeaderedBox>
                  ))}
                </div>
              </div>
            ))}
          </div>
        }
        right={
          <CenteredCard emoji="🗂️" title="Extracted Data">
            <div className="mb-8 space-y-4">
              <p>
                Below the sources is data automatically extracted from those documents, alongside
                what Wikidata already has.
              </p>
              <p>
                Each new item includes the source text used as evidence, and a link to view the full
                document.
              </p>
            </div>
            <TutorialActions
              skipHref={startHref}
              onSkip={() => startSession()}
              buttonText="Next"
              onNext={advance}
            />
          </CenteredCard>
        }
      />
    )
  }

  if (step === TutorialStep.GiveItATry) {
    return (
      <CenteredCard emoji="🎯" title="Give It a Try">
        <p className="mb-8">
          Compare the extracted data to the source. If they match, accept. If they don&apos;t,
          reject.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  // Interactive evaluation steps — all share the same structure
  const evalStep = tutorialEvaluationSteps[step]
  if (evalStep) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title={evalStep.success.title}
          message={evalStep.success.message}
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title={evalStep.error.title}
          message={evalStep.error.message}
          hint={evalStep.error.hint}
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[evalStep.politician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(evalStep.politician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={isStepComplete(actions, evalStep)}
              onSubmit={() => setCheckResult(checkStep(actions, evalStep))}
              onBack={() => setStep(evalStep.backStep)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={evalStep.isAdvancedMode}
        entitySearches={evalStep.entitySearches}
      />
    )
  }

  if (step === TutorialStep.MultipleSources) {
    return (
      <CenteredCard emoji="📚" title="Multiple Sources">
        <p className="mb-8">
          Sometimes information comes from different source documents. Next, try switching between
          these to evaluate all statements.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.SpecificOverGeneric) {
    return (
      <CenteredCard emoji="🎯" title="Specific Over Generic">
        <p className="mb-8">
          Specific data is better than generic data. If a more specific version already exists,
          reject the generic extraction.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.BasicKeyTakeaways) {
    return (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            Accept data that matches the source. Reject data that doesn&apos;t match or is less
            specific than what we already have.
          </p>
          <p>
            Not sure about something? That&apos;s completely fine — just skip it. You&apos;re never
            required to decide on every item.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It!"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  // ============ ADVANCED TUTORIAL STEPS ============
  if (step === TutorialStep.AdvancedWelcome) {
    return (
      <CenteredCard emoji="⚡" title="Advanced Mode Tutorial">
        <div className="mb-8 space-y-4">
          <p>
            Welcome to advanced mode! You now have the power to add new data and deprecate existing
            data.
          </p>
          <p>
            This lets you fill in gaps in the extracted data and replace generic data with more
            specific information.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's Advance"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.AddingNewData) {
    return (
      <CenteredCard emoji="🫥" title="Adding New Data">
        <p className="mb-8">
          Sometimes a source implies data that wasn&apos;t automatically extracted. Next, try adding
          the missing data yourself.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.ReplacingGenericData) {
    return (
      <CenteredCard emoji="🔄" title="Replacing Generic Data">
        <div className="mb-8 space-y-4">
          <p>
            Sometimes existing data is to generic and could be replaced with something more
            specific.
          </p>
          <p>
            In these cases, you can deprecate the existing data and accept the more specific
            extraction.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.DataWithMetadata) {
    return (
      <CenteredCard emoji="⚠️" title="Data With Metadata">
        <div className="mb-8 space-y-4">
          <p>
            Some existing Wikidata statements have valuable metadata: references (sources) and
            qualifiers (like start/end dates).
          </p>
          <p>
            When you deprecate such data, this metadata is lost. Sometimes it&apos;s better to add
            your new data via PoliLoom, then manually edit Wikidata to preserve the metadata.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={advance}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.AdvancedKeyTakeaways) {
    return (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            If a source implies data that wasn&apos;t extracted, use the &quot;+ Add&quot; buttons
            to create it yourself.
          </p>
          <p>
            Feel free to deprecate generic or incorrect existing data when you have better, more
            specific information.
          </p>
          <p>
            When existing data has references or qualifiers, consider whether that metadata is
            valuable. You might want to add your data first, then edit Wikidata manually to preserve
            the metadata.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It!"
          onNext={advance}
        />
      </CenteredCard>
    )
  }
}
