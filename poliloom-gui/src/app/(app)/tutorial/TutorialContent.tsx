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
import { PropertyActionItem, CreatePropertyItem, PropertyType } from '@/types'
import { actionToEvaluation, groupPropertiesIntoSections } from '@/lib/evaluation'
import {
  tutorialSources,
  extractedDataPolitician,
  birthDatePolitician,
  multipleSourcesPolitician,
  genericVsSpecificPolitician,
  deprecateSimplePolitician,
  deprecateWithMetadataPolitician,
  addNewDataPolitician,
  tutorialEntitySearches,
} from './tutorialData'

// Expected answers for each evaluation step
type ExpectedEvaluations = Record<string, boolean>

const birthDateExpected: ExpectedEvaluations = {
  'tutorial-birth-date': true, // Accept - March 15, 1975 is correct
  'tutorial-birth-date-incorrect': false, // Reject - June 8, 1952 is the mother's birth date
}

const multipleSourcesExpected: ExpectedEvaluations = {
  'tutorial-position-1': true, // Accept - Member of Parliament
  'tutorial-position-2': true, // Accept - Minister of Education
}

const genericVsSpecificExpected: ExpectedEvaluations = {
  'tutorial-generic-position': false, // Reject - generic "Member of Parliament" when specific exists
  'tutorial-existing-specific-position': true, // Keep - don't deprecate the existing specific data
}
const genericVsSpecificRequiredKeys = ['tutorial-generic-position']

// Advanced tutorial expected answers
const deprecateSimpleExpected: ExpectedEvaluations = {
  'tutorial-existing-generic-no-metadata': false, // Deprecate - generic with no metadata
  'tutorial-new-specific-position': true, // Accept - specific replacement
}
const deprecateSimpleRequiredKeys = ['tutorial-new-specific-position']

const deprecateWithMetadataExpected: ExpectedEvaluations = {
  'tutorial-new-specific-with-source': true, // Accept the new specific data
  'tutorial-existing-with-metadata': true, // Keep - don't deprecate (metadata is valuable)
}
const deprecateWithMetadataRequiredKeys = ['tutorial-new-specific-with-source']

/** Check whether all required property keys have been acted on (accept/reject/deprecate). */
function hasActionsForKeys(actions: PropertyActionItem[], keys: string[]): boolean {
  return keys.every((key) => actions.some((a) => a.action !== 'create' && a.id === key))
}

interface EvaluationResult {
  isCorrect: boolean
  mistakes: string[]
}

function checkEvaluations(
  actions: PropertyActionItem[],
  expected: ExpectedEvaluations,
): EvaluationResult {
  const mistakes: string[] = []

  for (const [key, expectedValue] of Object.entries(expected)) {
    const actualValue = actionToEvaluation(actions, key)
    // For existing data (where expected is true = keep), only count as mistake if user deprecated it
    // If the key has no action, that means "keep" which is correct
    if (expectedValue === true && actualValue === undefined) {
      continue
    }
    if (actualValue !== expectedValue) {
      mistakes.push(key)
    }
  }

  return {
    isCorrect: mistakes.length === 0,
    mistakes,
  }
}

function checkCreateAction(
  actions: PropertyActionItem[],
  expectedType: string,
  expectedEntityId: string,
): EvaluationResult {
  const createAction = actions.find(
    (a): a is CreatePropertyItem => a.action === 'create' && a.type === expectedType,
  )
  if (!createAction) {
    return { isCorrect: false, mistakes: ['no-create'] }
  }
  if (createAction.entity_id !== expectedEntityId) {
    return { isCorrect: false, mistakes: ['wrong-entity'] }
  }
  return { isCorrect: true, mistakes: [] }
}

// Tutorial steps as an enum so we can reorder/insert without renumbering
export enum TutorialStep {
  // Basic tutorial
  Welcome,
  WhyYourHelpMatters,
  SourceDocuments,
  SourcesAndAddSource,
  ExtractedData,
  GiveItATry,
  BirthDateEvaluation,
  MultipleSources,
  MultipleSourcesEvaluation,
  SpecificOverGeneric,
  SpecificOverGenericEvaluation,
  BasicKeyTakeaways,
  // Advanced tutorial
  AdvancedWelcome,
  AddingNewData,
  AddNewDataEvaluation,
  ReplacingGenericData,
  DeprecateSimpleEvaluation,
  DataWithMetadata,
  DataWithMetadataEvaluation,
  AdvancedKeyTakeaways,
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
  const getStartingStep = (): number => {
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

  if (step === TutorialStep.BirthDateEvaluation) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Excellent!"
          message="You correctly identified that March 15, 1975 matches the source, while June 8, 1952 was actually the mother's birth date. Reading carefully makes all the difference!"
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title="Not Quite Right"
          message="Take another look at the source document. One birth date belongs to Jane Doe, and the other belongs to someone else mentioned in the text."
          hint="Hint: Look carefully at who each date refers to in the source text."
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[birthDatePolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(birthDatePolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={hasActionsForKeys(actions, Object.keys(birthDateExpected))}
              onSubmit={() => setCheckResult(checkEvaluations(actions, birthDateExpected))}
              onBack={() => setStep(TutorialStep.GiveItATry)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={false}
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

  if (step === TutorialStep.MultipleSourcesEvaluation) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Great Job!"
          message="You correctly verified both positions from their respective source documents. Being able to work with multiple sources is an important skill!"
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title="Let's Try Again"
          message={`Make sure to check each position against its source document. Click "View" to switch between sources and verify each extraction.`}
          hint="Hint: Both positions are correctly extracted from their sources in this example."
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[multipleSourcesPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(multipleSourcesPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={hasActionsForKeys(actions, Object.keys(multipleSourcesExpected))}
              onSubmit={() => setCheckResult(checkEvaluations(actions, multipleSourcesExpected))}
              onBack={() => setStep(TutorialStep.MultipleSources)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={false}
      />
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

  if (step === TutorialStep.SpecificOverGenericEvaluation) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Perfect!"
          message={`You correctly rejected the generic "Member of Parliament" because the more specific "Member of Springfield Parliament" already exists. Quality over quantity!`}
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title="Almost There"
          message="Remember: when we already have specific data, we don't need a generic version. Look at what data already exists before accepting new extractions."
          hint={`Hint: "Member of Springfield Parliament" is more specific than "Member of Parliament".`}
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[genericVsSpecificPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(genericVsSpecificPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={hasActionsForKeys(actions, genericVsSpecificRequiredKeys)}
              onSubmit={() => setCheckResult(checkEvaluations(actions, genericVsSpecificExpected))}
              onBack={() => setStep(TutorialStep.SpecificOverGeneric)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={false}
      />
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
      <CenteredCard emoji="➕" title="Adding New Data">
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

  if (step === TutorialStep.AddNewDataEvaluation) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Nice Work!"
          message='You correctly identified that Jane Doe is a "Member of Springfield Parliament" and added it as new data. This is how you can fill in gaps in the extracted data!'
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title="Not Quite Right"
          message="Check the source document — it's a directory of Springfield Parliament members. Jane Doe needs a position that matches."
          hint='Hint: Click "+ Add Position", search for "Member of Springfield Parliament", and add it.'
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[addNewDataPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(addNewDataPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={actions.some((a) => a.action === 'create' && a.type === PropertyType.P39)}
              onSubmit={() =>
                setCheckResult(checkCreateAction(actions, PropertyType.P39, 'Q1343573'))
              }
              onBack={() => setStep(TutorialStep.AddingNewData)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={true}
        entitySearches={tutorialEntitySearches}
      />
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

  if (step === TutorialStep.DeprecateSimpleEvaluation) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Well Done!"
          message={
            'You correctly deprecated the generic "Member of Parliament" and accepted the more specific "Member of Springfield Parliament". Nice work!'
          }
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title="Not Quite Right"
          message={`The existing "Member of Parliament" is generic. The new extraction gives us more specific information - deprecate the old and accept the new.`}
          hint="Hint: Deprecate the generic existing data and accept the specific new extraction."
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[deprecateSimplePolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(deprecateSimplePolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={hasActionsForKeys(actions, deprecateSimpleRequiredKeys)}
              onSubmit={() => setCheckResult(checkEvaluations(actions, deprecateSimpleExpected))}
              onBack={() => setStep(TutorialStep.ReplacingGenericData)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={true}
      />
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

  if (step === TutorialStep.DataWithMetadataEvaluation) {
    if (checkResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Great Choice!"
          message="You accepted the new specific data and kept the existing data with its valuable metadata. Well done!"
          onNext={advance}
        />
      )
    }
    if (checkResult) {
      return (
        <ErrorFeedback
          title="Let's Reconsider"
          message="The new data is good, but the existing data has rich metadata attached. Deprecating it means losing all of that."
          hint="Hint: Accept the new extraction and keep the existing. Merge them manually in Wikidata later."
          onRetry={() => setCheckResult(null)}
        />
      )
    }
    return (
      <EvaluationView
        politicians={[deprecateWithMetadataPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(deprecateWithMetadataPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              isComplete={hasActionsForKeys(actions, deprecateWithMetadataRequiredKeys)}
              onSubmit={() =>
                setCheckResult(checkEvaluations(actions, deprecateWithMetadataExpected))
              }
              onBack={() => setStep(TutorialStep.DataWithMetadata)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
        isAdvancedMode={true}
      />
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
